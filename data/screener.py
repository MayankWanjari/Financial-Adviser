"""screener.py — Fundamental stock screener for Nifty 50 constituents.

Scans through Nifty 50 stocks and filters by PE ratio, ROE, debt-to-equity,
market cap, and sector. Returns matching stock dicts in the same shape as
get_stock_snapshot() so the agent can present them in a table.

PERFORMANCE NOTE: Screening all 50 stocks takes roughly 1-2 minutes because
yfinance is called one stock at a time with a 1-second delay to avoid
Yahoo Finance rate limiting. The agent should warn the user to wait.
"""

import time
from pathlib import Path

from data.stock_data import get_stock_snapshot

_PROJECT_ROOT     = Path(__file__).parent.parent
_NIFTY50_PATH     = _PROJECT_ROOT / "config" / "nifty50.txt"
_MIDCAP150_PATH   = _PROJECT_ROOT / "config" / "midcap150.txt"

# Delay between yfinance calls. 1 second keeps us well under rate limits.
_FETCH_DELAY_SECONDS = 1.0


def _load_tickers_from_file(path: Path, label: str) -> list[str]:
    """Read NSE ticker symbols from a plain-text config file, one ticker per line."""
    if not path.exists():
        raise FileNotFoundError(
            f"{label} ticker list not found at: {path}\n"
            f"Expected {path.name} with one NSE ticker per line."
        )
    tickers = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tickers.append(line.upper())
    if not tickers:
        raise ValueError(
            f"{path.name} is empty or contains only comments. Cannot run screener."
        )
    return tickers


def load_nifty50_tickers(path: Path = _NIFTY50_PATH) -> list[str]:
    """
    Read Nifty 50 ticker symbols from config/nifty50.txt.

    Returns:
        List of uppercase ticker strings, e.g. ['RELIANCE', 'TCS', ...].

    Raises:
        FileNotFoundError: If nifty50.txt doesn't exist.
        ValueError: If the file is empty or contains only comments.
    """
    return _load_tickers_from_file(path, "Nifty 50")


def load_midcap150_tickers(path: Path = _MIDCAP150_PATH) -> list[str]:
    """
    Read Nifty Midcap 150 ticker symbols from config/midcap150.txt.

    Returns:
        List of uppercase ticker strings.

    Raises:
        FileNotFoundError: If midcap150.txt doesn't exist.
        ValueError: If the file is empty or contains only comments.
    """
    return _load_tickers_from_file(path, "Nifty Midcap 150")


def screen_stocks(filters: dict, on_progress=None) -> tuple[list[dict], list[str]]:
    """
    Screen Indian stocks by fundamental criteria.

    Fetches each stock one at a time with a 1-second pause between requests.
    With ~50 stocks (Nifty 50) this takes roughly 1-2 minutes; with midcap150
    or "both" it will take proportionally longer. Stocks that fail to fetch
    (bad ticker, network error) are skipped.

    Args:
        filters: A dict with any combination of the following keys.
            All keys are optional — omit a key to skip that filter.

            pe_max         (float) — maximum trailing P/E ratio
            pe_min         (float) — minimum trailing P/E ratio
            roe_min        (float) — minimum ROE in %, e.g. 15 means >= 15% ROE
            de_max         (float) — maximum D/E ratio, e.g. 1.0 means <= 1x
            market_cap_min (float) — minimum market cap in ₹ Crore
            sector         (str)   — sector name to filter by (case-insensitive
                                     substring match, e.g. "Technology")
            universe       (str)   — "nifty50" (default), "midcap150", or "both"
        on_progress: Optional callback function with signature (current, total, ticker)

    Returns:
        (results, failed) where:
          results is a list of stock snapshot dicts that passed the filters.
          failed is a list of tickers that could not be fetched due to errors.

    Raises:
        FileNotFoundError: If the required ticker file is missing.
        ValueError: If the ticker file is empty, or universe value is unrecognised.
    """
    universe = (filters.get("universe") or "nifty50").strip().lower()

    if universe == "nifty50":
        tickers = load_nifty50_tickers()
    elif universe == "midcap150":
        tickers = load_midcap150_tickers()
    elif universe == "both":
        tickers = list(dict.fromkeys(
            load_nifty50_tickers() + load_midcap150_tickers()
        ))  # dict.fromkeys preserves order while removing duplicates
    else:
        raise ValueError(
            f"Unknown universe '{universe}'. "
            "Use 'nifty50', 'midcap150', or 'both'."
        )

    # Parse filter values once — each is None if not provided
    pe_max         = filters.get("pe_max")
    pe_min         = filters.get("pe_min")
    roe_min        = filters.get("roe_min")         # user passes as %, e.g. 15
    de_max         = filters.get("de_max")
    market_cap_min = filters.get("market_cap_min")  # user passes in ₹ Crore
    sector_filter  = (filters.get("sector") or "").strip().lower()

    results: list[dict] = []
    failed: list[str] = []
    total = len(tickers)

    for i, ticker in enumerate(tickers, start=1):
        if on_progress:
            on_progress(i, total, ticker)

        # Fetch — track failed tickers
        try:
            data = get_stock_snapshot(ticker)
        except Exception:
            data = None
            failed.append(ticker)

        # Always sleep between calls (skip after the very last ticker)
        if i < total:
            time.sleep(_FETCH_DELAY_SECONDS)

        if data is None:
            continue

        # ── Apply filters ──────────────────────────────────────────────────────
        # Convention: if the stock's value for a filtered field is None (missing
        # data from yfinance), the stock fails that filter rather than passes.
        # This avoids surfacing incomplete data as if it met the criteria.

        passes = True

        # P/E upper bound
        if pe_max is not None:
            pe = data.get("pe_trailing")
            if pe is None or pe > pe_max:
                passes = False

        # P/E lower bound (useful for "not overvalued" filters)
        if passes and pe_min is not None:
            pe = data.get("pe_trailing")
            if pe is None or pe < pe_min:
                passes = False

        # ROE: stored as decimal (0.15 = 15%), user supplies as % (15)
        if passes and roe_min is not None:
            roe = data.get("roe")
            if roe is None or (roe * 100) < roe_min:
                passes = False

        # D/E ratio: already normalized to standard convention in get_stock_snapshot
        if passes and de_max is not None:
            de = data.get("de_ratio")
            if de is None or de > de_max:
                passes = False

        # Market cap: stored in raw rupees; convert to crore for comparison
        if passes and market_cap_min is not None:
            mc = data.get("market_cap")
            if mc is None or (mc / 1_00_00_000) < market_cap_min:
                passes = False

        # Sector: case-insensitive substring match so "Technology" matches "IT"
        # sectors like "Technology" or "Consumer Technology"
        if passes and sector_filter:
            stock_sector = (data.get("sector") or "").lower()
            if sector_filter not in stock_sector:
                passes = False

        if passes:
            results.append(data)

    return results, failed
