"""stock_data.py — Refactored stock data module for the AI agent
================================================================
Pure data-fetching functions for NSE stocks via yfinance.
All functions return dicts/lists — no printing, no sys.exit().
Errors are raised as exceptions so callers can handle them gracefully.

Refactored from:
    stage2_stock_data/stock_snapshot.py   — single-stock fetch + formatters
    stage2_stock_data/watchlist_tracker.py — multi-stock fetch + 52W calc

Usage in agent:
    from data.stock_data import get_stock_snapshot, get_multiple_stocks
    data = get_stock_snapshot("RELIANCE")
    results, failed = get_multiple_stocks(["RELIANCE", "TCS", "INFY"])
"""

import time
import yfinance as yf
from pathlib import Path

from data.cache import cache_get, cache_set, STOCK_TTL


# ─────────────────────────────────────────────────────────────────
# NUMBER FORMATTING HELPERS
# These are used by the agent to format values for display.
# They handle all the Indian-market quirks (crore notation,
# div yield already being a %, D/E normalization, etc.)
# ─────────────────────────────────────────────────────────────────

def _indian_number_format(n: float) -> str:
    """
    Format an integer using Indian comma convention.

    Indian grouping: last 3 digits, then groups of 2 going left.
    Example: 19254000  →  '1,92,54,000'
             1925400   →  '19,25,400'
    """
    n = int(round(n))
    s = str(n)

    if len(s) <= 3:
        return s

    # Anchor the rightmost 3 digits, then add groups of 2 going left
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result  # Take up to 2 digits from the left chunk
        s = s[:-2]
    return result


def fmt_crore(raw_value) -> str:
    """
    Convert a raw rupee amount to ₹ Crore string.

    yfinance returns marketCap in raw rupees (e.g. 19,25,40,00,00,000).
    1 Crore = 1,00,00,000 = 10^7. We write it as 1_00_00_000 so the
    Indian grouping is visible in the source code itself.
    """
    if raw_value is None:
        return "N/A"
    crore = raw_value / 1_00_00_000        # Divide by 10^7 to get crores
    return f"₹{_indian_number_format(crore)} Cr"


def fmt_price(value) -> str:
    """Format a rupee price with 2 decimal places and comma separators."""
    if value is None:
        return "N/A"
    return f"₹{value:,.2f}"


def fmt_pct(decimal_value) -> str:
    """
    Format a decimal fraction as a percentage.

    yfinance returns ratios like ROE and margins as plain decimals:
    0.092  →  '9.20%'
    0.35   →  '35.00%'
    """
    if decimal_value is None:
        return "N/A"
    return f"{decimal_value * 100:.2f}%"


def fmt_ratio(value, decimals: int = 2) -> str:
    """Format a plain numeric ratio (P/E, P/B, D/E) to N decimal places."""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


def fmt_div_yield(value) -> str:
    """
    Format a dividend yield returned by yfinance.

    NOTE: yfinance's dividendYield is already a percentage, NOT a decimal.
    A value of 0.40 means 0.40%, NOT 40%. Do NOT multiply by 100 here.
    This is different from ROE/margins (which ARE decimals needing * 100).

    Adds a warning for implausibly high values — real Indian stocks rarely
    exceed 8-10% yield, so anything above 25% almost certainly signals
    a data glitch from Yahoo Finance.
    """
    if value is None:
        return "N/A"
    formatted = f"{value:.2f}%"
    if value > 25:
        # Flag it but still show the number so the user can investigate
        formatted += "  (verify - unusually high)"
    return formatted


# ─────────────────────────────────────────────────────────────────
# WATCHLIST FILE READER
# ─────────────────────────────────────────────────────────────────

def read_watchlist(path: Path) -> list[str]:
    """
    Read NSE ticker symbols from a plain-text file, one per line.

    Lines starting with '#' and blank lines are silently skipped.
    Returns uppercase stripped ticker strings (no .NS suffix).

    Args:
        path: Path object pointing to the watchlist file.

    Returns:
        List of ticker strings, e.g. ['RELIANCE', 'TCS', 'INFY'].

    Raises:
        FileNotFoundError: If the watchlist file does not exist.
        ValueError: If the file exists but contains no valid tickers.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Watchlist file not found: {path}\n"
            f"Create '{path.name}' and add one NSE ticker per line."
        )

    tickers = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Split on '#' to handle "TICKER  # Alt Name" format
                # from config/watchlist.txt — only keep the ticker part
                ticker = line.split("#")[0].strip().upper()
                if ticker:
                    tickers.append(ticker)

    if not tickers:
        raise ValueError(
            f"'{path.name}' is empty or contains only comments. "
            f"Add at least one NSE ticker symbol."
        )

    return tickers


# ─────────────────────────────────────────────────────────────────
# SINGLE-STOCK FETCH
# ─────────────────────────────────────────────────────────────────

def get_stock_snapshot(ticker: str) -> dict:
    """
    Fetch fundamental data for one NSE ticker from Yahoo Finance.

    Args:
        ticker: NSE symbol WITHOUT suffix (e.g. 'RELIANCE').
                The '.NS' suffix is appended automatically.

    Returns:
        A dict with all fundamental fields. Individual missing fields
        are stored as None (the agent can format these as 'N/A').
        Keys: ticker, symbol, name, sector, industry,
              current_price, change_abs, change_pct, week52_high, week52_low,
              market_cap, pe_trailing, pb_ratio, div_yield,
              roe, op_margin, net_margin, de_ratio, promoter_holding.

    Raises:
        ValueError: If the ticker is not found on Yahoo Finance
                    (unrecognised symbol or delisted stock).
        ConnectionError: If the Yahoo Finance API cannot be reached
                         (network failure, timeout, SSL error, etc.).
    """
    # Basic sanity-check before hitting the network.
    # Ticker symbols are short codes — nothing over 20 chars is valid.
    ticker = ticker.strip().upper()
    import re
    if not ticker or len(ticker) > 20 or not re.match(r'^[A-Z0-9&-]+$', ticker):
        raise ValueError(
            f"'{ticker}' doesn't look like a valid ticker symbol. "
            f"Use short NSE codes like RELIANCE, TCS, or M&M."
        )

    # ── Cache check — skip the network call if data is fresh ───────
    cache_key = f"stock_snapshot_{ticker}"
    cached = cache_get(cache_key, STOCK_TTL)
    if cached is not None:
        return cached

    full_ticker = f"{ticker}.NS"

    # ── Step 1: Download the info dict from Yahoo Finance ──────────
    # Retry logic for transient yfinance errors (timeouts, rate limits)
    max_retries = 2
    info = None
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            stock = yf.Ticker(full_ticker)
            # .info is a large dict (~100 fields) returned by Yahoo Finance.
            # We only use a small subset of it below.
            info = stock.info
            # Valid data should at least have a company name
            if info.get("longName") or info.get("shortName"):
                break
            # If name is missing but we didn't throw an error, it might be a valid
            # empty response (bad ticker), so we also break here.
            break
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                time.sleep(2)  # Wait 2 seconds before retrying
                continue
            
    if info is None and last_exception is not None:
        # Catches network timeouts, SSL errors, DNS failures, etc.
        raise ConnectionError(
            f"Could not reach Yahoo Finance for '{full_ticker}' after {max_retries+1} attempts. "
            f"Check your internet connection. Detail: {last_exception}"
        ) from last_exception


    # ── Step 2: Validate the ticker ────────────────────────────────
    # For an unknown ticker, yfinance returns a near-empty dict with no
    # company name. 'longName' is the most reliable field to check.
    company_name = info.get("longName") or info.get("shortName")
    if not company_name:
        raise ValueError(
            f"'{full_ticker}' was not found on Yahoo Finance. "
            f"Use the NSE ticker symbol (e.g. RELIANCE, TCS, HDFCBANK). "
            f"Look up the correct symbol at nseindia.com."
        )

    # ── Step 3: Compute price change ───────────────────────────────
    # yfinance uses different key names depending on market hours —
    # we try both variants and take whichever is available.
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    prev_close    = info.get("previousClose") or info.get("regularMarketPreviousClose")

    if current_price is not None and prev_close is not None and prev_close != 0:
        change_abs = current_price - prev_close
        change_pct = (change_abs / prev_close) * 100
    else:
        change_abs = None
        change_pct = None

    # ── Step 4: Normalize D/E ratio ────────────────────────────────
    # yfinance is INCONSISTENT with debtToEquity — sometimes it returns
    # the value as a percentage (42.0 meaning 0.42x) and sometimes as a
    # raw ratio (0.42 meaning 0.42x). There's no flag to tell which.
    #
    # Heuristic: real D/E ratios above 10x are extremely rare for listed
    # companies (even highly leveraged ones rarely exceed 5x). So if the
    # raw value is > 10, it's almost certainly in percentage form and we
    # divide by 100. Otherwise we treat it as already in standard form.
    raw_de = info.get("debtToEquity")
    if raw_de is not None:
        de_ratio = raw_de / 100.0 if raw_de > 10 else raw_de
    else:
        de_ratio = None

    # ── Step 5: Assemble result ──────────────────────────────────────
    result = {
        "ticker":           full_ticker,
        "symbol":           ticker,
        "name":             company_name,
        "sector":           info.get("sector")   or "N/A",
        "industry":         info.get("industry") or "N/A",

        # ── Price ──
        "current_price":    current_price,
        "change_abs":       change_abs,
        "change_pct":       change_pct,
        "week52_high":      info.get("fiftyTwoWeekHigh"),
        "week52_low":       info.get("fiftyTwoWeekLow"),

        # ── Valuation ──
        "market_cap":       info.get("marketCap"),
        "pe_trailing":      info.get("trailingPE"),
        "pb_ratio":         info.get("priceToBook"),
        "div_yield":        info.get("dividendYield"),   # already a %, e.g. 0.40 = 0.40%
        "eps_trailing":     info.get("trailingEps"),     # ₹ per share; needed for Graham Number
        "book_value":       info.get("bookValue"),       # ₹ per share; needed for Graham Number

        # ── Quality ──
        "roe":              info.get("returnOnEquity"),  # decimal, e.g. 0.092
        "op_margin":        info.get("operatingMargins"),# decimal
        "net_margin":       info.get("profitMargins"),   # decimal

        # ── Leverage ──
        "de_ratio":         de_ratio,

        # ── Promoter holding ──
        # NOT available via yfinance for Indian stocks (Yahoo doesn't carry it).
        # Future: fetch from NSE shareholding disclosures or Screener.in
        "promoter_holding": None,
    }

    cache_set(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────────
# MULTI-STOCK FETCH
# ─────────────────────────────────────────────────────────────────

# Small pause between yfinance calls to reduce the chance of rate-limiting.
# Increase to 2–3 if you see 429 errors.
_FETCH_DELAY_SECONDS = 1


def get_multiple_stocks(tickers: list[str]) -> tuple[list[dict], list[str]]:
    """
    Fetch stock data for a list of tickers, skipping any that fail.

    Unlike the legacy fetch_all() in watchlist_tracker.py, this function
    does NOT print progress to the terminal — the agent handles all display.
    Failed tickers are silently collected so the rest of the batch succeeds.

    Args:
        tickers: List of NSE symbols without .NS suffix.

    Returns:
        A tuple of (results, failed):
            results — list of dicts from get_stock_snapshot(), one per
                      successful ticker.
            failed  — list of ticker strings that raised an exception
                      (bad symbol, network error, etc.).
    """
    results: list[dict] = []
    failed:  list[str]  = []
    total = len(tickers)

    for i, ticker in enumerate(tickers, start=1):
        try:
            data = get_stock_snapshot(ticker)
            results.append(data)
        except (ValueError, ConnectionError, Exception):
            # Log silently — the agent can mention failed tickers in its reply.
            failed.append(ticker.upper())

        # Small pause between calls — skip on the last ticker.
        if i < total:
            time.sleep(_FETCH_DELAY_SECONDS)

    return results, failed


# ─────────────────────────────────────────────────────────────────
# CALCULATIONS
# ─────────────────────────────────────────────────────────────────

def compute_from_52w_high(data: dict) -> float | None:
    """
    Return how far the current price is below its 52-week high, as a %.

    Result is always <= 0 (e.g. -15.4 means 15.4% below the high).
    A result of 0.0 means the stock is AT its 52-week high right now.
    Returns None if current_price or week52_high is missing.

    Args:
        data: A dict returned by get_stock_snapshot().
    """
    price = data.get("current_price")
    high  = data.get("week52_high")
    if price is not None and high is not None and high != 0:
        return ((price - high) / high) * 100
    return None
