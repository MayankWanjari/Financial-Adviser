"""pe_bands.py — Historical PE band analysis for Indian stocks.

Answers: "Is this stock cheap or expensive relative to its own history?"

Approach: yfinance provides daily close prices going back years, but NOT historical
EPS. So we use today's trailing EPS as a fixed divisor across the full price history.
This gives a rough approximation of how PE has varied as the price moved — NOT the
true historical PE (which would need historical earnings). The caveat is always
included in the result so the user understands the limitation.

All functions return dicts — no printing, no sys.exit().
"""

import statistics
from pathlib import Path

import yfinance as yf

from data.cache import cache_get, cache_set

# Cache PE band results for 1 hour — the band itself doesn't change minute-to-minute
_PE_BANDS_TTL = 3600


# ─── Pure computation helpers (testable without network) ──────────────────────

def _pe_position_label(
    current_pe: float | None,
    pe_25th: float,
    pe_median: float,
    pe_75th: float,
) -> str:
    """
    Classify a stock's current PE relative to its historical percentile bands.

    Returns:
        'cheap'          — current PE below the 25th percentile
        'fair'           — between 25th and median
        'expensive'      — between median and 75th
        'very_expensive' — above the 75th percentile
        'unknown'        — current PE is None (unavailable)
    """
    if current_pe is None:
        return "unknown"
    if current_pe < pe_25th:
        return "cheap"
    if current_pe < pe_median:
        return "fair"
    if current_pe < pe_75th:
        return "expensive"
    return "very_expensive"


def get_pe_history(ticker: str, years: int = 5) -> dict:
    """
    Compute historical PE bands for an NSE stock using daily close prices.

    Since yfinance only provides current trailing EPS (not historical EPS), this
    function divides every historical close price by today's EPS. The result shows
    how the stock's implied PE has moved as its PRICE changed — but it doesn't
    account for EPS growth over the period. Treat the output as directional.

    Args:
        ticker: NSE ticker without .NS suffix, e.g. 'RELIANCE'.
        years:  Number of years of price history to use. Default 5.
                Capped at 10 to keep the request fast.

    Returns:
        A dict with:
            ticker          (str)
            name            (str)
            years_requested (int)
            data_points     (int)   — number of trading days in the history
            current_pe      (float | None)
            pe_high         (float) — max implied PE in the period
            pe_low          (float) — min implied PE in the period
            pe_median       (float) — median implied PE
            pe_25th         (float) — 25th percentile (cheap threshold)
            pe_75th         (float) — 75th percentile (expensive threshold)
            current_position (str)  — "cheap" / "fair" / "expensive" / "very_expensive"
            interpretation  (str)   — one-line plain-English summary
            caveat          (str)   — data-quality warning

    Raises:
        ValueError:      If ticker not found, EPS is missing/negative, or
                         price history is too short to be meaningful.
        ConnectionError: If Yahoo Finance cannot be reached.
    """
    years = min(max(years, 1), 10)  # Clamp to [1, 10]
    ticker = ticker.strip().upper()

    cache_key = f"pe_bands_{ticker}_{years}y"
    cached = cache_get(cache_key, _PE_BANDS_TTL)
    if cached is not None:
        return cached

    full_ticker = f"{ticker}.NS"

    # ── Fetch info (name + EPS) ───────────────────────────────────────────────
    try:
        stock = yf.Ticker(full_ticker)
        info  = stock.info
    except Exception as e:
        raise ConnectionError(
            f"Could not reach Yahoo Finance for '{full_ticker}'. "
            f"Check your internet connection. Detail: {e}"
        ) from e

    name = info.get("longName") or info.get("shortName")
    if not name:
        raise ValueError(
            f"'{full_ticker}' not found on Yahoo Finance. "
            f"Use the NSE ticker symbol, e.g. RELIANCE, TCS, HDFCBANK."
        )

    eps = info.get("trailingEps")
    if eps is None:
        raise ValueError(
            f"Trailing EPS not available for {ticker} on Yahoo Finance. "
            f"PE band analysis requires EPS data. "
            f"This is common for PSUs and some smaller companies."
        )
    if eps <= 0:
        raise ValueError(
            f"PE band analysis requires positive EPS. "
            f"{ticker} has EPS={eps:.2f} — a loss-making company cannot be valued by PE."
        )

    current_pe_raw = info.get("trailingPE")

    # ── Fetch price history ───────────────────────────────────────────────────
    try:
        hist = stock.history(period=f"{years}y")
    except Exception as e:
        raise ConnectionError(
            f"Could not fetch price history for '{full_ticker}'. Detail: {e}"
        ) from e

    if hist.empty or len(hist) < 20:
        raise ValueError(
            f"Not enough price history for {ticker} "
            f"(got {len(hist)} data points, need at least 20). "
            f"Try a shorter period or check the ticker."
        )

    # ── Compute implied PE for each historical close ──────────────────────────
    # Divide each day's close price by current trailing EPS.
    # This approximates "what PE would this price imply at today's earnings level?"
    # It's directional, not historical-accurate.
    closes   = hist["Close"].dropna().tolist()
    pe_series = [round(price / eps, 2) for price in closes if price > 0]

    if not pe_series:
        raise ValueError(f"Could not compute PE series for {ticker}.")

    pe_series_sorted = sorted(pe_series)
    n = len(pe_series_sorted)

    pe_low    = pe_series_sorted[0]
    pe_high   = pe_series_sorted[-1]
    pe_median = statistics.median(pe_series_sorted)
    pe_25th   = pe_series_sorted[int(n * 0.25)]
    pe_75th   = pe_series_sorted[int(n * 0.75)]

    current_pe = current_pe_raw  # Use the live PE directly from .info (most accurate)

    # ── Determine position and interpretation ─────────────────────────────────
    position = _pe_position_label(current_pe, pe_25th, pe_median, pe_75th)

    if position == "unknown":
        interp = (
            f"Current PE not available. Historical range: {pe_low:.1f}x – {pe_high:.1f}x "
            f"(median {pe_median:.1f}x)."
        )
    elif position == "cheap":
        interp = (
            f"At {current_pe:.1f}x, {ticker} is in the cheapest 25% of its {years}-year PE range "
            f"({pe_low:.1f}x – {pe_high:.1f}x, median {pe_median:.1f}x). "
            f"Historically inexpensive on this measure."
        )
    elif position == "fair":
        interp = (
            f"At {current_pe:.1f}x, {ticker} is below its {years}-year median PE of {pe_median:.1f}x "
            f"— in the lower half of its historical range ({pe_low:.1f}x – {pe_high:.1f}x). "
            f"Reasonably priced by its own history."
        )
    elif position == "expensive":
        interp = (
            f"At {current_pe:.1f}x, {ticker} is above its {years}-year median PE of {pe_median:.1f}x "
            f"— in the upper half of its historical range ({pe_low:.1f}x – {pe_high:.1f}x). "
            f"On the pricier side relative to its own history."
        )
    else:  # very_expensive
        interp = (
            f"At {current_pe:.1f}x, {ticker} is in the most expensive 25% of its {years}-year PE range "
            f"({pe_low:.1f}x – {pe_high:.1f}x, median {pe_median:.1f}x). "
            f"Historically expensive — worth understanding why."
        )

    result = {
        "ticker":           ticker,
        "name":             name,
        "years_requested":  years,
        "data_points":      len(pe_series),
        "current_pe":       round(current_pe, 2) if current_pe is not None else None,
        "pe_high":          round(pe_high, 2),
        "pe_low":           round(pe_low, 2),
        "pe_median":        round(pe_median, 2),
        "pe_25th":          round(pe_25th, 2),
        "pe_75th":          round(pe_75th, 2),
        "current_position": position,
        "interpretation":   interp,
        "caveat": (
            "PE bands use today's trailing EPS applied across historical prices. "
            "Actual historical EPS was different — EPS grows over time, so historical "
            "PEs were likely higher than shown here. Treat these bands as directional, not precise."
        ),
    }

    cache_set(cache_key, result)
    return result
