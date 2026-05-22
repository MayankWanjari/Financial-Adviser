"""
news_fetcher.py — Fetch, filter, deduplicate, and tag RSS headlines.

This is the "data collection" layer for the news pipeline. It:
  1. Loads RSS feed URLs from config/feeds.json (not hardcoded)
  2. Pulls news from all feeds in parallel (faster than one-by-one)
  3. Keeps only articles published in the last 24 hours
  4. Merges near-duplicate headlines (same story, different wording) into one
     entry and records how many sources covered it — a signal of importance
  5. Tags any headline that mentions a stock from config/watchlist.txt

Refactored from stage1_news/rss_fetcher.py. Key changes vs the legacy version:
  - FEEDS list moved out of code into config/feeds.json (editable without touching code)
  - SYMBOL_NAME_MAP moved out of code into config/watchlist.txt (TICKER  # Alt, Names format)
  - No sys.exit(), no print() — raises exceptions instead
  - fetch_headlines() now takes a feeds_path argument alongside watchlist_path

Nothing in this file calls the AI or writes to disk — it just returns clean data.
"""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from pathlib import Path

import feedparser  # pip install feedparser

# ─── Deduplication threshold ──────────────────────────────────────────────────
#
# Two headlines are considered duplicates if they are at least this similar
# (on a 0.0–1.0 scale, where 1.0 = identical).
#
# HOW TO TUNE:
#   Raise toward 0.90 if unrelated stories are being incorrectly merged.
#   Lower toward 0.60 if the same story keeps appearing multiple times.
#   0.75 is a reasonable starting point for financial news headlines.
#
DEDUP_SIMILARITY_THRESHOLD = 0.75

# ─── Logging ──────────────────────────────────────────────────────────────────
# WARNING level means we only surface problems, not routine info. Change to
# logging.DEBUG if you want verbose output while developing.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ─── Config loaders ───────────────────────────────────────────────────────────


def _load_feeds(feeds_path: Path) -> list[dict]:
    """
    Load the RSS feed list from a JSON file.

    Expected format: a JSON array of objects, each with "url" and "source" keys.
    Example:
        [{"url": "https://...", "source": "Economic Times"}, ...]

    Args:
        feeds_path: Path to feeds.json.

    Raises:
        FileNotFoundError: If the JSON file doesn't exist.
        ValueError: If the JSON is malformed or the array is empty.
    """
    if not feeds_path.exists():
        raise FileNotFoundError(
            f"Feeds config not found: {feeds_path}\n"
            f"Create '{feeds_path.name}' as a JSON array of {{url, source}} objects."
        )

    try:
        feeds = json.loads(feeds_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"'{feeds_path.name}' contains invalid JSON: {exc}") from exc

    if not isinstance(feeds, list) or not feeds:
        raise ValueError(
            f"'{feeds_path.name}' must be a non-empty JSON array of "
            f"{{\"url\": \"...\", \"source\": \"...\"}} objects."
        )

    return feeds


def _parse_watchlist_file(watchlist_path: Path) -> list[tuple[str, list[str]]]:
    """
    Parse watchlist.txt and return a list of (ticker, alt_names) pairs.

    Handles two line formats:
      RELIANCE                          → ('RELIANCE', [])
      RELIANCE  # Reliance Ind, RIL     → ('RELIANCE', ['Reliance Ind', 'RIL'])

    Lines starting with '#' (pure comment lines) and blank lines are skipped.
    The '#' character on a ticker line is the alt-names delimiter, not a comment.

    If the file doesn't exist, logs a warning and returns an empty list
    (watchlist tagging will be skipped, but the rest of the pipeline continues).
    """
    if not watchlist_path.exists():
        logger.warning(
            "watchlist.txt not found at %s — no watchlist tagging.", watchlist_path
        )
        return []

    entries = []
    for line in watchlist_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        # Skip blank lines and pure comment lines (lines that START with #)
        if not stripped or stripped.startswith("#"):
            continue

        # Split on the first '#' to separate ticker from alternate names
        if "#" in stripped:
            ticker_part, names_part = stripped.split("#", 1)
            ticker = ticker_part.strip().upper()
            # Build the alt names list, dropping any empty items after splitting
            alt_names = [n.strip() for n in names_part.split(",") if n.strip()]
        else:
            ticker = stripped.upper()
            alt_names = []

        if ticker:
            entries.append((ticker, alt_names))

    return entries


def build_symbol_name_map(watchlist_path: Path) -> dict[str, list[str]]:
    """
    Build a symbol → alternate names dict from watchlist.txt.

    This is the refactored equivalent of the old SYMBOL_NAME_MAP constant in
    rss_fetcher.py. The agent and news_analyzer use this to know what names to
    look for in headlines when checking the user's watchlist.

    Returns a dict like:
        {
            "RELIANCE":   ["Reliance Industries", "RIL"],
            "TCS":        ["Tata Consultancy", "Tata Consultancy Services"],
            "HDFCBANK":   ["HDFC Bank"],
            ...
        }

    Tickers with no alt-name column still appear in the dict with an empty list.

    Args:
        watchlist_path: Path to watchlist.txt.
    """
    return {
        ticker: alt_names
        for ticker, alt_names in _parse_watchlist_file(watchlist_path)
    }


# ─── Internal helper functions ────────────────────────────────────────────────


def _parse_timestamp(entry: feedparser.FeedParserDict) -> datetime:
    """
    Extract the published datetime from a feed entry and return it as a
    timezone-aware UTC datetime object.

    feedparser stores parsed timestamps in 'published_parsed' as a
    time.struct_time (Python's basic time tuple). We convert that to a
    proper datetime. If the timestamp is missing or broken, we fall back
    to 'one hour ago' so the article isn't unfairly excluded by the 24h filter.
    """
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            # published_parsed is already in UTC per the feedparser docs
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            pass  # Bad timestamp — fall through to fallback

    # Fallback: assume the article is recent so it isn't filtered out
    logger.debug("No valid timestamp for '%s', assuming recent.", entry.get("title", ""))
    return datetime.now(timezone.utc) - timedelta(hours=1)


def _fetch_single_feed(feed_info: dict) -> dict:
    """
    Download and parse one RSS feed.

    Returns a result dict with these keys:
      articles  (list[dict])  — parsed article dicts, may be empty
      source    (str)         — human-readable feed name
      url       (str)         — the feed URL that was fetched
      success   (bool)        — True if at least some entries were parsed
      raw_count (int)         — number of entries parsed (before 24h filter)
      error     (str | None)  — error description if success=False, else None

    If the feed fails completely, articles is [] and success is False.
    If the feed has XML issues but still returned some entries, articles is
    populated and success is True (we use whatever we got).
    """
    url    = feed_info["url"]
    source = feed_info["source"]
    articles: list[dict] = []
    error_msg: str | None = None
    success = True

    try:
        feed = feedparser.parse(url)

        if feed.bozo:
            exc_name = type(feed.bozo_exception).__name__
            if not feed.entries:
                # The feed is completely unusable: network failure or unparseable XML
                success = False
                error_msg = f"{exc_name}: {feed.bozo_exception}"
                logger.warning("Feed '%s' failed (%s) — skipping.", source, exc_name)
                return {
                    "articles":  [],
                    "source":    source,
                    "url":       url,
                    "success":   False,
                    "raw_count": 0,
                    "error":     error_msg,
                }
            else:
                # Bozo with partial entries: bad XML but feedparser salvaged something
                logger.warning(
                    "Feed '%s' has XML issues (%s) but returned %d entries — using them.",
                    source, exc_name, len(feed.entries),
                )

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue  # Skip entries with no title — not useful

            articles.append({
                "title":     title,
                "summary":   entry.get("summary", entry.get("description", "")).strip(),
                "link":      entry.get("link", ""),
                "published": _parse_timestamp(entry),
                "source":    source,  # Single string here; becomes a list after dedup
            })

        logger.debug("Fetched %d articles from %s", len(articles), source)

    except Exception as exc:
        # Catch-all: network timeouts, SSL errors, unexpected feedparser errors
        success = False
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.warning("Failed to fetch '%s': %s", source, exc)

    return {
        "articles":  articles,
        "source":    source,
        "url":       url,
        "success":   success,
        "raw_count": len(articles),
        "error":     error_msg,
    }


def _is_within_24h(article: dict) -> bool:
    """Return True if the article was published within the last 24 hours (UTC)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    return article["published"] >= cutoff


def _headline_similarity(title_a: str, title_b: str) -> float:
    """
    Return a 0.0–1.0 similarity score between two headline strings.
    1.0 = identical, 0.0 = completely different.

    Uses Python's built-in difflib.SequenceMatcher — no extra packages needed.
    Comparison is case-insensitive.
    """
    return SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()


def _deduplicate(articles: list[dict]) -> list[dict]:
    """
    Merge near-duplicate headlines, tracking all source names for each story.

    Algorithm:
      For each article, compare it against every already-kept article.
        - If similarity >= DEDUP_SIMILARITY_THRESHOLD: it's a duplicate.
          Merge: add the new source to the kept article's 'sources' list.
          Use the earlier of the two publish times.
        - If no match found: it's a new unique story. Add it to the kept list.

    After this function, each article has a 'sources' list instead of a single
    'source' string. A long sources list means the story was widely covered —
    the AI uses this as a signal of importance.
    """
    unique: list[dict] = []

    for article in articles:
        matched = False

        for kept in unique:
            if _headline_similarity(article["title"], kept["title"]) >= DEDUP_SIMILARITY_THRESHOLD:
                # Duplicate found — merge sources
                if article["source"] not in kept["sources"]:
                    kept["sources"].append(article["source"])
                # Keep the earliest publish time
                if article["published"] < kept["published"]:
                    kept["published"] = article["published"]
                matched = True
                break

        if not matched:
            # New unique story — copy the dict and convert 'source' → 'sources' list
            new_entry = article.copy()
            new_entry["sources"] = [new_entry.pop("source")]
            unique.append(new_entry)

    return unique


def _matches_symbol_or_name(text: str, symbol: str, alt_names: list[str]) -> bool:
    """
    Return True if 'text' contains the symbol or any of its alt_names as a whole word.

    Uses regex word boundaries (\\b) to avoid false positives.
    Example without \\b: "TCS" would match inside "tactics" — wrong.
    Example with \\b:    "TCS" only matches when surrounded by non-word characters.
    """
    all_names = [symbol] + alt_names
    for name in all_names:
        # re.escape handles names with special characters (e.g., "L&T")
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _tag_watchlist(
    articles: list[dict],
    symbols: list[str],
    symbol_name_map: dict[str, list[str]],
) -> list[dict]:
    """
    For each article, find which watchlist stocks it mentions.

    Adds a 'watchlist_hits' key to every article: a list of symbol strings
    (empty list if no watchlist stocks are mentioned).

    Matching checks both the symbol itself (e.g., "TCS") and any alternate
    names from symbol_name_map (e.g., "Tata Consultancy Services").

    Args:
        articles:        Deduplicated article list.
        symbols:         Ticker list from the watchlist file.
        symbol_name_map: Dict of ticker → alternate names, from build_symbol_name_map().
    """
    for article in articles:
        # Search both title and summary
        search_text = f"{article['title']} {article.get('summary', '')}"
        hits = []

        for symbol in symbols:
            alt_names = symbol_name_map.get(symbol, [])
            if _matches_symbol_or_name(search_text, symbol, alt_names):
                hits.append(symbol)

        article["watchlist_hits"] = hits

    return articles


# ─── Public API ───────────────────────────────────────────────────────────────


def fetch_headlines(
    watchlist_path: Path,
    feeds_path: Path,
) -> tuple[list[dict], list[str], list[dict]]:
    """
    Main entry point for this module. Call this from the agent's news tool.

    Steps:
      1. Load the RSS feed list from feeds_path (JSON)
      2. Load watchlist symbols + alternate names from watchlist_path
      3. Fetch all RSS feeds in parallel using threads
      4. Filter to articles published in the last 24 hours
      5. Deduplicate near-identical headlines
      6. Tag articles that mention watchlist stocks

    Args:
        watchlist_path: Path to config/watchlist.txt
        feeds_path:     Path to config/feeds.json

    Returns:
        A tuple of three values:
          articles (list[dict])
            Cleaned, deduped, tagged articles. Each dict has:
              title (str), summary (str), link (str), published (datetime),
              sources (list[str]), watchlist_hits (list[str])

          symbols (list[str])
            The watchlist symbols that were loaded (passed to the AI so it
            knows what to look for in section 8 of the briefing).

          feed_results (list[dict])
            One entry per feed, with keys:
              source (str), url (str), success (bool),
              raw_count (int), fresh_count (int), error (str|None)
            Used by the agent to report feed health if needed.

    Raises:
        FileNotFoundError: If feeds_path doesn't exist.
        ValueError: If feeds.json is malformed or empty.
    """
    # Step 1: Load feeds config from JSON
    feeds = _load_feeds(feeds_path)

    # Step 2: Load watchlist — get both the ticker list and the name map in one pass
    entries = _parse_watchlist_file(watchlist_path)
    symbols = [ticker for ticker, _ in entries]
    symbol_name_map = {ticker: alt_names for ticker, alt_names in entries}

    # Step 3: Fetch all feeds in parallel
    # ThreadPoolExecutor runs each _fetch_single_feed call in its own thread.
    # max_workers = number of feeds means they all start at the same time.
    all_articles: list[dict] = []
    raw_feed_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(feeds)) as executor:
        futures = {executor.submit(_fetch_single_feed, feed): feed for feed in feeds}
        for future in as_completed(futures):
            result = future.result()
            # Count how many articles from this feed pass the 24h filter
            # (before global dedup, so this reflects the feed's raw contribution)
            fresh_count = sum(1 for a in result["articles"] if _is_within_24h(a))
            raw_feed_results.append({
                "source":      result["source"],
                "url":         result["url"],
                "success":     result["success"],
                "raw_count":   result["raw_count"],
                "fresh_count": fresh_count,
                "error":       result["error"],
            })
            all_articles.extend(result["articles"])

    # Sort feed_results alphabetically so the health summary is consistent
    feed_results = sorted(raw_feed_results, key=lambda r: r["source"])

    # Step 4: Keep only the last 24 hours
    recent = [a for a in all_articles if _is_within_24h(a)]

    # Step 5: Deduplicate
    deduped = _deduplicate(recent)

    # Step 6: Tag watchlist mentions
    tagged = _tag_watchlist(deduped, symbols, symbol_name_map)

    # Sort newest first so the AI sees the most recent news at the top
    tagged.sort(key=lambda a: a["published"], reverse=True)

    return tagged, symbols, feed_results
