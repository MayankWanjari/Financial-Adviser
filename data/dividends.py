"""
data/dividends.py — Dividend history analysis for Indian stocks.

Answers: "Has this company paid consistent / growing dividends?"

Uses yfinance's .dividends property (a pandas Series of payout dates and amounts).
Aggregates to annual totals, computes CAGR, and classifies consistency.

All functions return dicts — no printing, no sys.exit().
"""

from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

from data.cache import cache_get, cache_set

# Cache for 1 hour — dividend history doesn't change intraday
_DIV_TTL = 3600


# ─── Pure computation helpers (testable without network) ──────────────────────

def _calculate_cagr(earliest: float, latest: float, n: int) -> float | None:
    """
    Compute Compound Annual Growth Rate between two dividend values.

    Args:
        earliest: Dividend amount in the first year.
        latest:   Dividend amount in the last year.
        n:        Number of intervals (years between first and last, not count of years).

    Returns:
        CAGR as a decimal (e.g. 0.12 = 12%), rounded to 4 places.
        None if either value is zero/negative or n is not positive.
    """
    if earliest <= 0 or latest <= 0 or n <= 0:
        return None
    return round((latest / earliest) ** (1 / n) - 1, 4)


def _classify_consistency(
    annual_dict: dict[int, float],
    cutoff_year: int,
    current_year: int,
) -> str:
    """
    Classify dividend payout consistency over the requested window.

    Args:
        annual_dict:  {year: total_dividend} for all years that had payouts.
        cutoff_year:  The year before the window starts (exclusive).
        current_year: The current calendar year (inclusive upper bound).

    Returns:
        'Growing'    — paid every year, amounts non-decreasing
        'Consistent' — paid every year, but not strictly growing
        'Irregular'  — at least one expected year was missed
    """
    expected_years = set(range(cutoff_year + 1, current_year + 1))
    paid_years = set(annual_dict.keys())

    if expected_years and expected_years <= paid_years:
        sorted_amounts = [annual_dict[yr] for yr in sorted(annual_dict.keys())]
        is_growing = all(
            sorted_amounts[i] >= sorted_amounts[i - 1]
            for i in range(1, len(sorted_amounts))
        )
        return "Growing" if is_growing else "Consistent"

    return "Irregular"


def get_dividend_history(ticker: str, years: int = 5) -> dict:
    """
    Fetch and analyse a stock's dividend payout history.

    Uses yfinance's Ticker.dividends (a pandas Series) to build a year-by-year
    picture of payouts. Computes annual totals, CAGR, yield, and consistency label.

    Args:
        ticker: NSE ticker without .NS suffix, e.g. 'ITC'.
        years:  How many calendar years to look back. Default 5. Clamped to [1, 15].

    Returns:
        A dict with:
            ticker              (str)
            name                (str)
            years_requested     (int)
            annual_dividends    (list[dict])  — [{year: int, total_dividend: float}, ...]
                                               sorted oldest → newest
            dividend_growth_cagr (float | None) — annualised growth rate (e.g. 0.12 = 12%).
                                               None if fewer than 2 years of data.
            current_yield       (float | None) — trailing dividend yield (%) from yfinance info
            payout_consistency  (str)  — "Growing" | "Consistent" | "Irregular" | "No dividends"
            interpretation      (str)  — plain-English one-paragraph summary
            message             (str | None) — set only when no dividends were found at all

    Raises:
        ValueError:      If ticker not found on Yahoo Finance.
        ConnectionError: If Yahoo Finance cannot be reached.
    """
    ticker = ticker.strip().upper()
    years  = min(max(years, 1), 15)

    cache_key = f"dividends_{ticker}_{years}y"
    cached = cache_get(cache_key, _DIV_TTL)
    if cached is not None:
        return cached

    full_ticker = f"{ticker}.NS"

    # ── Fetch info (name + current yield) ────────────────────────────────────
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
            f"Use the NSE ticker symbol, e.g. ITC, COALINDIA, HDFCBANK."
        )

    # dividendYield in yfinance is already a percentage value (e.g. 3.2 = 3.2%)
    current_yield: float | None = info.get("dividendYield")

    # ── Fetch dividend history ────────────────────────────────────────────────
    try:
        div_series = stock.dividends
    except Exception as e:
        raise ConnectionError(
            f"Could not fetch dividend data for '{full_ticker}'. Detail: {e}"
        ) from e

    # ── Filter to requested year window ──────────────────────────────────────
    cutoff_year = datetime.now(timezone.utc).year - years
    # div_series index may be tz-aware or tz-naive depending on yfinance version
    annual: dict[int, float] = {}

    if div_series is not None and not div_series.empty:
        for dt_index, amount in div_series.items():
            # Normalise timezone-aware timestamps
            if hasattr(dt_index, "year"):
                year = dt_index.year
            else:
                continue  # Skip if index is not a date type

            if year <= cutoff_year:
                continue

            annual[year] = round(annual.get(year, 0.0) + float(amount), 4)

    # ── No dividends case ─────────────────────────────────────────────────────
    if not annual:
        result = {
            "ticker":               ticker,
            "name":                 name,
            "years_requested":      years,
            "annual_dividends":     [],
            "dividend_growth_cagr": None,
            "current_yield":        current_yield,
            "payout_consistency":   "No dividends",
            "interpretation": (
                f"{name} ({ticker}) has not paid any dividends in the last {years} years. "
                f"This is common for growth-oriented companies that reinvest all earnings."
            ),
            "message": (
                f"No dividend payments found for {ticker} in the last {years} years. "
                f"The company may reinvest profits rather than distributing them."
            ),
        }
        cache_set(cache_key, result)
        return result

    # ── Build sorted annual list ──────────────────────────────────────────────
    annual_list = [
        {"year": yr, "total_dividend": annual[yr]}
        for yr in sorted(annual.keys())
    ]

    # ── CAGR ─────────────────────────────────────────────────────────────────
    cagr: float | None = None
    if len(annual_list) >= 2:
        cagr = _calculate_cagr(
            annual_list[0]["total_dividend"],
            annual_list[-1]["total_dividend"],
            len(annual_list) - 1,
        )

    # ── Payout consistency ────────────────────────────────────────────────────
    consistency = _classify_consistency(annual, cutoff_year, datetime.now(timezone.utc).year)

    # ── Interpretation ────────────────────────────────────────────────────────
    cagr_str = f"{cagr * 100:.1f}%" if cagr is not None else "N/A"
    yield_str = f"{current_yield:.2f}%" if current_yield else "N/A"

    if consistency == "Growing":
        interp = (
            f"{name} has paid growing dividends for {len(annual_list)} consecutive year(s) "
            f"with ~{cagr_str} annual growth. "
            f"Current yield of {yield_str} "
            + ("is above market average (≥2%)." if current_yield and current_yield >= 2
               else "is modest but consistent.")
        )
    elif consistency == "Consistent":
        interp = (
            f"{name} has paid dividends every year for {len(annual_list)} year(s) "
            f"but growth has been flat or uneven (CAGR {cagr_str}). "
            f"Current yield: {yield_str}."
        )
    elif consistency == "Irregular":
        interp = (
            f"{name} has paid dividends in some years but skipped others over the last "
            f"{years} years — payout is irregular. "
            f"Current yield: {yield_str}. "
            f"Check company announcements for the reason behind gaps."
        )
    else:
        interp = f"{name} has not paid dividends in the last {years} years."

    result = {
        "ticker":               ticker,
        "name":                 name,
        "years_requested":      years,
        "annual_dividends":     annual_list,
        "dividend_growth_cagr": cagr,
        "current_yield":        current_yield,
        "payout_consistency":   consistency,
        "interpretation":       interp,
    }

    cache_set(cache_key, result)
    return result
