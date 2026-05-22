"""agent/dispatch.py — Tool execution bridge between Gemini and data modules.

Maps Gemini's function_call requests to actual data/ module calls.
Each tool name maps to one or more functions in data/*.py.

To add a new tool:
  1. Add the FunctionDeclaration in agent/tools.py
  2. Add the dispatch case in handle_tool_call() below
"""

import re
import time
from datetime import datetime
from pathlib import Path

from data import (
    dividends,
    news_analyzer,
    news_fetcher,
    pe_bands,
    peers,
    portfolio,
    scorer,
    screener,
    stock_data,
    technicals,
    valuation,
)

# ─── Config file paths ────────────────────────────────────────────────────────
# __file__ is agent/dispatch.py, so .parent.parent = project root
_PROJECT_ROOT   = Path(__file__).parent.parent
_WATCHLIST_PATH = _PROJECT_ROOT / "config" / "watchlist.txt"
_FEEDS_PATH     = _PROJECT_ROOT / "config" / "feeds.json"

# Valid NSE ticker characters: uppercase letters, digits, ampersand, hyphen.
# Examples: RELIANCE, TCS, M&M, BAJAJ-AUTO. Max 25 chars covers all real tickers.
_TICKER_RE = re.compile(r'^[A-Z0-9&\-]{1,25}$')


def _validate_ticker(raw: str) -> str:
    """
    Normalise and validate a ticker string before it touches any file or network call.

    Strips whitespace, uppercases, then checks against _TICKER_RE so that
    newlines, semicolons, slashes, or other injected characters are rejected
    before they can corrupt watchlist.txt or cause confusing yfinance errors.

    Returns:
        The cleaned ticker string (e.g. 'reliance ' → 'RELIANCE').

    Raises:
        ValueError: If the ticker is empty or contains invalid characters.
    """
    ticker = raw.strip().upper()
    if not ticker:
        raise ValueError("Ticker cannot be empty.")
    if not _TICKER_RE.match(ticker):
        raise ValueError(
            f"'{ticker}' doesn't look like a valid NSE ticker. "
            "Use short codes like RELIANCE, TCS, M&M, or BAJAJ-AUTO "
            "(letters, digits, '&', and '-' only)."
        )
    return ticker


# ─── Watchlist file helpers ───────────────────────────────────────────────────
# These are pure file operations — they don't need access to the Gemini model.


def _read_watchlist_tickers() -> list[str]:
    """
    Read config/watchlist.txt and return just the ticker symbols.

    Parses both 'TICKER' and 'TICKER  # Alt Names' formats.
    Returns an empty list if the file doesn't exist.
    """
    if not _WATCHLIST_PATH.exists():
        return []
    tickers = []
    for line in _WATCHLIST_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Everything before the first '#' is the ticker
        ticker = stripped.split("#")[0].strip().upper()
        if ticker:
            tickers.append(ticker)
    return tickers


def _add_to_watchlist(ticker: str) -> str:
    """
    Append a ticker to watchlist.txt if it isn't already there.

    Preserves all existing content (comments, alt-names, blank lines).
    Returns a human-readable result message.
    """
    current = _read_watchlist_tickers()
    if ticker in current:
        return f"{ticker} is already in your watchlist."

    # Append the new ticker as a plain line (user can add alt-names manually later)
    with open(_WATCHLIST_PATH, "a", encoding="utf-8") as f:
        f.write(f"\n{ticker}\n")

    return f"{ticker} added to your watchlist."


def _remove_from_watchlist(ticker: str) -> str:
    """
    Remove all lines for a given ticker from watchlist.txt.

    Keeps every other line (comments, blank lines, other tickers) intact.
    Returns a human-readable result message.
    """
    if not _WATCHLIST_PATH.exists():
        return f"Watchlist file not found — can't remove {ticker}."

    lines = _WATCHLIST_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = []
    removed = False

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            line_ticker = stripped.split("#")[0].strip().upper()
            if line_ticker == ticker:
                removed = True
                continue  # Drop this line
        new_lines.append(line)

    if not removed:
        return f"{ticker} was not found in your watchlist."

    _WATCHLIST_PATH.write_text("".join(new_lines), encoding="utf-8")
    return f"{ticker} removed from your watchlist."


def _make_json_safe(obj):
    """
    Recursively convert a data object to be JSON-serializable.

    Needed because tool results may contain datetime objects (from RSS articles),
    and Gemini's FunctionResponse dict must be fully JSON-serializable.

    Converts: datetime → ISO 8601 string. Everything else passes through.
    """
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


# ─── Main dispatch function ──────────────────────────────────────────────────


def handle_tool_call(function_call, agent) -> dict:
    """
    Execute the data function that Gemini requested, and return the result.

    This is the bridge between Gemini (which decides WHAT to fetch) and the
    data/ modules (which actually fetch it). Each tool maps to one or more
    function calls in data/stock_data.py, data/news_fetcher.py, etc.

    Args:
        function_call: A Gemini FunctionCall proto with .name (str) and
                       .args (dict-like MapComposite).
        agent:         The FinancialAgent instance (used to set last_chart_ticker).

    Returns:
        A dict that is safe to pass back to Gemini as a FunctionResponse.
        Always has either a "result" key (success) or an "error" key (failure).
        The dict is serialization-safe (no datetime objects, etc.).
    """
    name = function_call.name
    args = dict(function_call.args)

    try:
        # ── Stock snapshot ───────────────────────────────────────────────
        if name == "get_stock_snapshot":
            ticker = args["ticker"].strip().upper()
            data = stock_data.get_stock_snapshot(ticker)
            agent.last_chart_ticker = ticker  # app.py uses this to render the price chart
            return {"result": data}

        # ── Stock comparison ─────────────────────────────────────────────
        elif name == "compare_stocks":
            results, failed = stock_data.get_multiple_stocks(args["tickers"])
            response: dict = {"result": results}
            if failed:
                response["failed"] = failed
            return response

        # ── Full market briefing ─────────────────────────────────────────
        elif name == "get_market_news":
            articles, symbols, feed_results = news_fetcher.fetch_headlines(
                _WATCHLIST_PATH, _FEEDS_PATH
            )
            if not articles:
                return {"result": "No news articles found in the last 24 hours. Try again later."}

            symbol_name_map = news_fetcher.build_symbol_name_map(_WATCHLIST_PATH)
            briefing = news_analyzer.analyze_headlines(articles, symbols, symbol_name_map)

            # Include feed health so Gemini can mention if any sources failed
            failed_feeds = [f["source"] for f in feed_results if not f["success"]]
            result: dict = {"briefing": briefing, "article_count": len(articles)}
            if failed_feeds:
                result["failed_feeds"] = failed_feeds
            return result

        # ── News for a specific stock ────────────────────────────────────
        elif name == "get_stock_news":
            ticker = args["ticker"].strip().upper()
            articles, _, _ = news_fetcher.fetch_headlines(_WATCHLIST_PATH, _FEEDS_PATH)

            # Get alternate names for this ticker so we can match on them too
            symbol_name_map = news_fetcher.build_symbol_name_map(_WATCHLIST_PATH)
            alt_names = [n.lower() for n in symbol_name_map.get(ticker, [])]

            matching = []
            for article in articles:
                search_text = (
                    f"{article['title']} {article.get('summary', '')}".lower()
                )
                # Method 1: the news_fetcher already tagged watchlist hits via regex
                already_tagged = ticker in [
                    h.upper() for h in article.get("watchlist_hits", [])
                ]
                # Method 2: simple substring match for non-watchlist tickers
                text_match = (
                    ticker.lower() in search_text
                    or any(name in search_text for name in alt_names)
                )
                if already_tagged or text_match:
                    matching.append(article)

            if not matching:
                return {
                    "result": [],
                    "message": (
                        f"No news found for {ticker} in the last 24 hours. "
                        "This could mean the stock wasn't mentioned in today's feeds, "
                        "or the ticker symbol is different from how it appears in headlines."
                    ),
                }

            # Serialize for Gemini (datetime → string, truncate long summaries)
            serializable = []
            for a in matching:
                serializable.append({
                    "title":     a["title"],
                    "sources":   a["sources"],
                    "published": a["published"].isoformat(),
                    "summary":   (a.get("summary") or "")[:250],
                    "link":      a.get("link", ""),
                })
            return {"result": serializable}

        # ── Watchlist read ───────────────────────────────────────────────
        elif name == "get_watchlist":
            tickers = _read_watchlist_tickers()
            return {"result": tickers}

        # ── Watchlist add ────────────────────────────────────────────────
        elif name == "add_to_watchlist":
            ticker = _validate_ticker(args["ticker"])
            msg = _add_to_watchlist(ticker)
            return {"result": msg}

        # ── Watchlist remove ─────────────────────────────────────────────
        elif name == "remove_from_watchlist":
            ticker = _validate_ticker(args["ticker"])
            msg = _remove_from_watchlist(ticker)
            return {"result": msg}

        # ── Valuation ────────────────────────────────────────────────────
        elif name == "calculate_valuation":
            summary = valuation.valuation_summary(args["ticker"].strip().upper())
            return {"result": summary}

        # ── Stock screener ───────────────────────────────────────────────
        elif name == "screen_stocks":
            # Pass all args directly as the filters dict.
            # Gemini only includes keys the user actually specified,
            # so this naturally handles optional parameters.
            on_progress = getattr(agent, "progress_callback", None)
            matches, failed = screener.screen_stocks(dict(args), on_progress=on_progress)
            if not matches:
                return {
                    "result": [],
                    "message": (
                        "No Nifty 50 stocks matched the given criteria. "
                        "Try relaxing the filters (e.g. raise pe_max or lower roe_min)."
                    ),
                }
            response_dict: dict = {"result": matches, "count": len(matches)}
            if failed:
                response_dict["note"] = (
                    f"{len(failed)} stocks failed to load and were skipped: "
                    f"{', '.join(failed[:5])}"
                    + (f" and {len(failed) - 5} more" if len(failed) > 5 else "")
                )
            return response_dict

        # ── Opportunity scorer — single stock ────────────────────────────
        elif name == "score_stock":
            ticker = args["ticker"].strip().upper()
            result = scorer.score_stock(ticker)
            # Strip raw_data to reduce payload size for Gemini
            result.pop("raw_data", None)
            return {"result": result}

        # ── Opportunity scanner — all Nifty 50 ──────────────────────────
        elif name == "find_opportunities":
            on_progress = getattr(agent, "progress_callback", None)
            results, failed = scorer.find_opportunities(on_progress=on_progress)
            if not results:
                return {
                    "result": [],
                    "message": (
                        "Could not score any Nifty 50 stocks — "
                        "check your internet connection and try again."
                    ),
                }
            # Build a COMPACT summary for Gemini — full results are too large
            # and cause empty responses (STOP with no text).
            # Only send top 10 with minimal fields + overall stats.
            top_10 = []
            for r in results[:10]:
                bd = r.get("breakdown", {})
                top_10.append({
                    "rank": len(top_10) + 1,
                    "ticker": r["ticker"],
                    "name": r["name"],
                    "score": r["total_score"],
                    "grade": r["grade"],
                    "pe": bd.get("value", {}).get("detail", "N/A"),
                    "roe": bd.get("quality", {}).get("detail", "N/A"),
                    "debt": bd.get("safety", {}).get("detail", "N/A"),
                    "insight": r.get("interpretation", ""),
                })
            # Grade distribution across ALL stocks
            grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
            for r in results:
                grades[r["grade"]] = grades.get(r["grade"], 0) + 1
            avg_score = round(sum(r["total_score"] for r in results) / len(results), 1)

            response_dict = {
                "top_10": top_10,
                "total_scanned": len(results),
                "avg_score": avg_score,
                "grade_distribution": grades,
                "note": "Showing top 10 of {} scored stocks. User can ask 'Score TICKER' for full detail on any stock.".format(len(results)),
            }
            if failed:
                response_dict["skipped"] = (
                    f"{len(failed)} stocks failed to load: {', '.join(failed[:5])}"
                )
            return response_dict

        # ── Bulk watchlist analysis ──────────────────────────────────────
        elif name == "analyze_watchlist":
            on_progress = getattr(agent, "progress_callback", None)
            tickers = _read_watchlist_tickers()
            if not tickers:
                return {
                    "result": [],
                    "message": "Your watchlist is empty. Add some stocks first.",
                }

            scored = []
            skipped = []  # Each entry: "TICKER (reason)"
            total = len(tickers)
            for i, ticker in enumerate(tickers):
                if on_progress:
                    on_progress(i + 1, total, ticker)
                try:
                    scored.append(scorer.score_stock(ticker))
                except Exception as exc:
                    # Record the reason so the user knows WHY a stock was skipped
                    skipped.append(f"{ticker} ({exc})")
                if i < total - 1:
                    time.sleep(1)

            if not scored:
                return {
                    "result": [],
                    "message": (
                        "Could not fetch data for any watchlist stock. "
                        "Check your internet connection. "
                        + (f"Failed: {'; '.join(skipped)}" if skipped else "")
                    ),
                }

            # Sort by score descending
            scored.sort(key=lambda x: x["total_score"], reverse=True)

            # Build compact results for Gemini (strip raw_data + breakdown)
            compact = []
            for s in scored:
                bd = s.get("breakdown", {})
                compact.append({
                    "ticker": s["ticker"],
                    "name": s["name"],
                    "score": s["total_score"],
                    "grade": s["grade"],
                    "pe": bd.get("value", {}).get("detail", "N/A"),
                    "roe": bd.get("quality", {}).get("detail", "N/A"),
                    "debt": bd.get("safety", {}).get("detail", "N/A"),
                    "insight": s.get("interpretation", ""),
                })

            # Summary statistics
            scores = [s["total_score"] for s in scored]
            summary = {
                "total_stocks":   len(scored),
                "avg_score":      round(sum(scores) / len(scores), 1),
                "top_performer":  compact[0]["ticker"] if compact else "N/A",
                "weakest":        compact[-1]["ticker"] if compact else "N/A",
            }
            response_dict = {"result": compact, "summary": summary}
            if skipped:
                response_dict["skipped"] = (
                    f"{len(skipped)} watchlist stocks failed to load: {', '.join(skipped)}"
                )
            return response_dict

        # ── Daily Master Report ──────────────────────────────────────────
        elif name == "generate_daily_master_report":
            # 1. Fetch Market News Briefing
            articles, symbols, feed_results = news_fetcher.fetch_headlines(_WATCHLIST_PATH, _FEEDS_PATH)
            symbol_name_map = news_fetcher.build_symbol_name_map(_WATCHLIST_PATH)
            briefing = news_analyzer.analyze_headlines(articles, symbols, symbol_name_map)

            # 2. Get Fundamentally Strong & Underrated Stocks
            on_progress = getattr(agent, "progress_callback", None)
            scored_stocks, _ = scorer.find_opportunities(on_progress=on_progress)

            top_picks = []
            if scored_stocks:
                # They are already sorted by total_score. Take the top 5.
                for r in scored_stocks[:5]:
                    bd = r.get("breakdown", {})
                    top_picks.append({
                        "ticker": r["ticker"],
                        "name": r["name"],
                        "score": r["total_score"],
                        "grade": r["grade"],
                        "pe": bd.get("value", {}).get("detail", "N/A"),
                        "roe": bd.get("quality", {}).get("detail", "N/A"),
                        "graham_margin": bd.get("graham_gap", {}).get("detail", "N/A"),
                        "insight": r.get("interpretation", "")
                    })

            return {
                "news_and_future_impact": briefing,
                "top_underrated_strong_picks_1_to_2_years": top_picks,
                "instructions_for_ai": "Synthesize a Daily Master Report. Section 1: Impacted Stocks & Future Market Trends (based on news). Section 2: Top 3-5 Underrated Fundamental Picks for 1-2 years (based on the provided top_picks data)."
            }

        # ── Portfolio — add holding ──────────────────────────────────────
        elif name == "add_portfolio_holding":
            msg = portfolio.add_holding(
                ticker    = args["ticker"],
                quantity  = int(args["quantity"]),
                avg_price = float(args["avg_price"]),
            )
            return {"result": msg}

        # ── Portfolio — remove holding ───────────────────────────────────
        elif name == "remove_portfolio_holding":
            msg = portfolio.remove_holding(args["ticker"])
            return {"result": msg}

        # ── Portfolio — full summary with live P&L ───────────────────────
        elif name == "get_portfolio_summary":
            summary = portfolio.portfolio_summary()
            return {"result": summary}

        # ── Historical PE bands ──────────────────────────────────────────
        elif name == "get_pe_history":
            ticker = args["ticker"].strip().upper()
            years  = int(args.get("years", 5))
            result = pe_bands.get_pe_history(ticker, years)
            return {"result": result}

        # ── Technical indicators ─────────────────────────────────────────
        elif name == "get_technicals":
            ticker = args["ticker"].strip().upper()
            result = technicals.get_technical_indicators(ticker)
            return {"result": result}

        # ── Sector peer comparison ───────────────────────────────────────
        elif name == "compare_with_peers":
            ticker = args["ticker"].strip().upper()
            result = peers.compare_with_peers(ticker)
            # Strip raw_data from target and all peers to keep payload compact
            if "target" in result and isinstance(result["target"], dict):
                result["target"].pop("raw_data", None)
            for p in result.get("peers", []):
                if isinstance(p, dict):
                    p.pop("raw_data", None)
            return {"result": result}

        # ── Dividend history ─────────────────────────────────────────────
        elif name == "get_dividend_history":
            ticker = args["ticker"].strip().upper()
            years  = int(args.get("years", 5))
            result = dividends.get_dividend_history(ticker, years)
            return {"result": result}

        else:
            return {"error": f"Unknown tool '{name}' — this is a bug."}

    except (ValueError, ConnectionError, RuntimeError, EnvironmentError,
            FileNotFoundError) as exc:
        # Known exceptions from data/ modules — return as an error the agent
        # can explain in natural language. Don't crash the chat.
        return {"error": str(exc)}

    except Exception as exc:
        # Unexpected error — still don't crash, but include the type for debugging
        return {"error": f"Unexpected error in {name}: {type(exc).__name__}: {exc}"}
