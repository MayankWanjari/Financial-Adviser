"""
rss_fetcher.py — Fetch, filter, deduplicate, and tag RSS headlines.

This is the "data collection" layer of Stage 1. It:
  1. Pulls news from 5 Indian financial RSS feeds in parallel (faster than one-by-one)
  2. Keeps only articles published in the last 24 hours
  3. Merges near-duplicate headlines (same story, different wording) into one entry
     and records how many sources covered it — a signal of importance
  4. Tags any headline that mentions a stock from your watchlist.txt

Nothing in this file calls the AI or writes to disk — it just returns clean data.
"""

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

# ─── RSS feed list ────────────────────────────────────────────────────────────
#
# Each entry needs a "url" (the feed URL) and a "source" (a short human-readable
# name that appears in the briefing). To add a new feed, just append to this list.
#
# FEED HISTORY (so future sessions know why these choices were made):
#   Removed — Moneycontrol Business/Markets: feeds parse OK but haven't updated
#              since April 2024. Completely stale as of 2026-05.
#   Removed — Business Standard: SAXParseException on all URL variants (broken feed).
#   Removed — Reuters Business: URLError (Reuters retired public RSS ~2020).
#   Added   — Hindu BusinessLine, CNBC TV18, NDTV Profit: tested working, fresh articles.
#
FEEDS = [
    {"url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "source": "Economic Times"},
    {"url": "https://www.livemint.com/rss/markets",                                 "source": "Livemint"},
    {"url": "https://www.thehindubusinessline.com/markets/?service=rss",            "source": "Hindu BusinessLine"},
    {"url": "https://www.cnbctv18.com/commonfeeds/v1/cne/rss/market.xml",          "source": "CNBC TV18"},
    {"url": "https://feeds.feedburner.com/ndtvprofit-latest",                      "source": "NDTV Profit"},
]

# ─── Symbol → common name mapping ────────────────────────────────────────────
#
# This dict maps NSE stock symbols to the names and abbreviations that typically
# appear in news headlines. The fetcher does a case-insensitive word-boundary
# search for each of these strings.
#
# PRECISION vs RECALL TRADE-OFF:
#   More names = more hits (higher recall) but also more false positives (lower
#   precision). Short or ambiguous tokens are the danger zone:
#
#   BAD:  "HDFCBANK": ["HDFC Bank", "HDFC"]
#         ↑ bare "HDFC" matches HDFC AMC, HDFC Life, HDFC Ltd Chairman news, etc.
#
#   GOOD: "HDFCBANK": ["HDFC Bank"]
#         ↑ only matches articles specifically about the bank
#
#   Rule of thumb: only include a name/token if it would NEVER appear in an
#   article about a *different* company. When in doubt, leave it out.
#   The NSE symbol (e.g., "HDFCBANK") is always searched automatically —
#   you don't need to repeat it in the list.
#
# HOW TO EXTEND:
#   Add your own stock:  "WIPRO": ["Wipro"],
#   Multiple names:      "BAJFINANCE": ["Bajaj Finance", "BAF"],
#
# This dict is also imported by ai_analyzer.py so the AI knows what to look for
# in the "Your Watchlist News" section of the briefing.
#
SYMBOL_NAME_MAP: dict[str, list[str]] = {
    "RELIANCE":   ["Reliance Industries", "RIL"],
    # NOTE: bare "Reliance" omitted — it also matches Reliance Power, Reliance Infra, etc.
    "TCS":        ["TCS", "Tata Consultancy", "Tata Consultancy Services"],
    "HDFCBANK":   ["HDFC Bank"],
    # NOTE: bare "HDFC" omitted — it matches HDFC AMC, HDFC Life, HDFC Ltd, etc.
    "INFY":       ["Infosys", "Infy"],
    "TATAMOTORS": ["Tata Motors"],
}

# ─── Logging ──────────────────────────────────────────────────────────────────
# WARNING level means we only print problems, not routine info. Change to
# logging.DEBUG if you want verbose output while developing.
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


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


def _load_watchlist(watchlist_path: Path) -> list[str]:
    """
    Read watchlist.txt and return a list of stock symbols (uppercase).

    Lines starting with '#' and blank lines are ignored.
    If the file doesn't exist, returns an empty list with a warning.
    """
    if not watchlist_path.exists():
        logger.warning("watchlist.txt not found at %s — no watchlist tagging.", watchlist_path)
        return []

    symbols = []
    for line in watchlist_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            symbols.append(line.upper())

    return symbols


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


def _tag_watchlist(articles: list[dict], symbols: list[str]) -> list[dict]:
    """
    For each article, find which watchlist stocks it mentions.

    Adds a 'watchlist_hits' key to every article: a list of symbol strings
    (empty list if no watchlist stocks are mentioned).

    Matching checks both the symbol itself (e.g., "TCS") and any alternate
    names from SYMBOL_NAME_MAP (e.g., "Tata Consultancy Services").
    """
    for article in articles:
        # Search both title and summary
        search_text = f"{article['title']} {article.get('summary', '')}"
        hits = []

        for symbol in symbols:
            alt_names = SYMBOL_NAME_MAP.get(symbol, [])
            if _matches_symbol_or_name(search_text, symbol, alt_names):
                hits.append(symbol)

        article["watchlist_hits"] = hits

    return articles


# ─── Public API ───────────────────────────────────────────────────────────────


def fetch_headlines(watchlist_path: Path) -> tuple[list[dict], list[str], list[dict]]:
    """
    Main entry point for this module. Call this from main.py.

    Steps:
      1. Load the watchlist from watchlist_path
      2. Fetch all RSS feeds in parallel using threads
      3. Filter to articles published in the last 24 hours
      4. Deduplicate near-identical headlines
      5. Tag articles that mention watchlist stocks

    Args:
        watchlist_path: Path to watchlist.txt

    Returns:
        A tuple of three values:
          articles (list[dict])
            Cleaned, deduped, tagged articles. Each dict has:
              title (str), summary (str), link (str), published (datetime),
              sources (list[str]), watchlist_hits (list[str])

          symbols (list[str])
            The watchlist symbols that were loaded (passed to the AI so it
            knows what to look for in the briefing).

          feed_results (list[dict])
            One entry per feed, with keys:
              source (str), url (str), success (bool),
              raw_count (int), fresh_count (int), error (str|None)
            Used by main.py to display the feed health summary.
    """
    # Step 1: Load watchlist
    symbols = _load_watchlist(watchlist_path)

    # Step 2: Fetch all feeds in parallel
    # ThreadPoolExecutor runs each _fetch_single_feed call in its own thread.
    # max_workers = number of feeds means they all start at the same time.
    all_articles: list[dict] = []
    raw_feed_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=len(FEEDS)) as executor:
        futures = {executor.submit(_fetch_single_feed, feed): feed for feed in FEEDS}
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

    # Step 3: Keep only the last 24 hours
    recent = [a for a in all_articles if _is_within_24h(a)]

    # Step 4: Deduplicate
    deduped = _deduplicate(recent)

    # Step 5: Tag watchlist mentions
    tagged = _tag_watchlist(deduped, symbols)

    # Sort newest first so the AI sees the most recent news at the top
    tagged.sort(key=lambda a: a["published"], reverse=True)

    return tagged, symbols, feed_results
