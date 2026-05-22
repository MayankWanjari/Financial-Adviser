"""valuation.py — Simple intrinsic value calculators for Indian stocks.

Three calculation models, plus a composite summary that pulls live data:

  graham_number()      — Benjamin Graham's classic formula (√(22.5 × EPS × BV))
  margin_of_safety()   — % gap between current price and an intrinsic value estimate
  pe_valuation()       — fair value by applying a benchmark PE to current earnings
  valuation_summary()  — fetches live data and runs all models for one ticker

IMPORTANT: These are rough estimates based on limited public data. Graham's formula
was designed for US stocks in the 1970s and is even rougher for Indian markets.
The agent is expected to explain limitations when presenting results.

All functions return floats or dicts — no printing, no sys.exit().
"""

import math
from data.stock_data import get_stock_snapshot

# Nifty 50 long-run average P/E used as a default benchmark when no
# sector-specific data is available. Real sector averages vary widely:
# IT ~25-30x, PSU Banks ~8-10x, FMCG ~40x+. This is just a rough anchor.
_DEFAULT_MARKET_PE = 22.0


# ─── Pure calculation functions ───────────────────────────────────────────────


def graham_number(eps: float, book_value: float) -> float:
    """
    Calculate Benjamin Graham's intrinsic value estimate.

    Formula: √(22.5 × EPS × BookValuePerShare)

    The constant 22.5 comes from Graham's two rules of thumb:
      - Never pay more than 15× earnings (PE ≤ 15)
      - Never pay more than 1.5× book value (PB ≤ 1.5)
      - 15 × 1.5 = 22.5

    The result is a rough price ceiling for a value investor.

    Args:
        eps:        Trailing twelve-month earnings per share (₹).
        book_value: Book value per share (₹).

    Returns:
        Estimated intrinsic value per share in ₹, always > 0.

    Raises:
        ValueError: If eps × book_value ≤ 0. The formula is undefined for
                    loss-making companies or those with negative equity.
    """
    product = 22.5 * eps * book_value
    if product <= 0:
        raise ValueError(
            f"Graham Number requires positive EPS and positive Book Value. "
            f"Got EPS={eps:.2f}, BookValue={book_value:.2f}. "
            f"Companies with losses or negative equity cannot be valued this way."
        )
    return math.sqrt(product)


def margin_of_safety(current_price: float, intrinsic_value: float) -> float:
    """
    Calculate the margin of safety as a percentage.

    Measures how much cushion there is between the market price and an
    estimated intrinsic value. Graham recommended a minimum 33% margin
    to protect against errors in the valuation estimate itself.

    Formula: (intrinsic_value − current_price) / intrinsic_value × 100

    Args:
        current_price:   Current market price per share (₹).
        intrinsic_value: Estimated intrinsic value per share (₹).

    Returns:
        Margin of safety as a float percentage.
        Positive → stock is below intrinsic value (potential upside).
        Negative → stock is above intrinsic value (priced at a premium).

    Raises:
        ValueError: If intrinsic_value is zero (avoids division by zero).
    """
    if intrinsic_value == 0:
        raise ValueError("Intrinsic value cannot be zero when computing margin of safety.")
    return (intrinsic_value - current_price) / intrinsic_value * 100


def pe_valuation(current_pe: float, eps: float, sector_avg_pe: float) -> dict:
    """
    Estimate fair value by applying a reference P/E to current earnings.

    Logic: if the market typically pays `sector_avg_pe` per ₹1 of earnings
    in this sector, then a fair price = sector_avg_pe × EPS.

    Args:
        current_pe:    The stock's trailing P/E ratio.
        eps:           Trailing twelve-month earnings per share (₹).
        sector_avg_pe: Reference P/E to use as the benchmark (e.g. sector
                       average, historical market average, etc.).

    Returns:
        A dict with:
            fair_value           (float) — sector_avg_pe × EPS in ₹
            premium_discount_pct (float) — how much current PE deviates from
                                           the benchmark; positive = premium,
                                           negative = discount
            current_pe           (float) — echoed back
            sector_avg_pe        (float) — echoed back

    Raises:
        ValueError: If sector_avg_pe ≤ 0 or eps ≤ 0.
    """
    if sector_avg_pe <= 0:
        raise ValueError(f"sector_avg_pe must be positive, got {sector_avg_pe}.")
    if eps <= 0:
        raise ValueError(
            f"PE-based fair value requires positive EPS. Got EPS={eps:.2f}. "
            "Cannot estimate fair value for a loss-making company this way."
        )

    fair_value = sector_avg_pe * eps
    premium_discount_pct = (current_pe - sector_avg_pe) / sector_avg_pe * 100

    return {
        "fair_value":            round(fair_value, 2),
        "premium_discount_pct":  round(premium_discount_pct, 2),
        "current_pe":            round(current_pe, 2),
        "sector_avg_pe":         round(sector_avg_pe, 2),
    }


# ─── Composite summary ────────────────────────────────────────────────────────


def valuation_summary(ticker: str) -> dict:
    """
    Full valuation snapshot for one NSE ticker.

    Fetches live fundamental data via get_stock_snapshot() and runs all
    valuation models that have the required inputs. Models are skipped
    gracefully when yfinance doesn't provide the needed field (common for
    some Indian stocks on Yahoo Finance).

    Args:
        ticker: NSE symbol without .NS suffix, e.g. 'RELIANCE'.

    Returns:
        A dict with:
            ticker        (str)
            name          (str)
            current_price (float | None)
            pe_trailing   (float | None)

            graham        (dict | None)  — present if EPS + Book Value available:
                number           (float) — Graham Number in ₹
                eps_used         (float) — EPS used in calculation
                book_value_used  (float) — Book Value used
                margin_of_safety (float | None) — % below/above Graham Number
                interpretation   (str)   — plain-English reading of the numbers

            graham_skip_reason (str) — present instead of 'graham' if skipped

            pe_based      (dict | None) — present if PE + EPS available:
                fair_value           (float) — benchmark_pe × EPS
                premium_discount_pct (float) — deviation from benchmark
                current_pe           (float)
                benchmark_pe         (float)
                benchmark_note       (str)   — explains what PE was used
                interpretation       (str)

            pe_skip_reason (str) — present instead of 'pe_based' if skipped

            raw (dict) — full get_stock_snapshot() dict for reference

    Raises:
        ValueError:      If ticker not found on Yahoo Finance.
        ConnectionError: If Yahoo Finance cannot be reached.
    """
    data = get_stock_snapshot(ticker)

    result: dict = {
        "ticker":        data["symbol"],
        "name":          data["name"],
        "current_price": data.get("current_price"),
        "pe_trailing":   data.get("pe_trailing"),
        "raw":           data,
    }

    price = data.get("current_price")
    eps   = data.get("eps_trailing")
    bv    = data.get("book_value")
    pe    = data.get("pe_trailing")

    # ── Graham Number ─────────────────────────────────────────────────────────
    if eps is not None and bv is not None:
        try:
            gn  = graham_number(eps, bv)
            mos = margin_of_safety(price, gn) if price is not None else None

            if mos is not None:
                if mos >= 33:
                    interp = (
                        f"The stock is {mos:.1f}% below the Graham Number of ₹{gn:.0f}. "
                        "Graham considered a >33% margin of safety as good value — "
                        "meaning there's room for error in the estimate."
                    )
                elif mos >= 0:
                    interp = (
                        f"The stock is {mos:.1f}% below the Graham Number of ₹{gn:.0f}. "
                        "It's within intrinsic value but the safety margin is thin — "
                        "the estimate would need to be roughly correct to make sense."
                    )
                else:
                    interp = (
                        f"The stock is {abs(mos):.1f}% ABOVE the Graham Number of ₹{gn:.0f}. "
                        "By this measure it appears overvalued — though Graham's formula "
                        "was designed for different markets and may understate value for "
                        "high-growth or asset-light businesses."
                    )
            else:
                interp = "Price data unavailable — margin of safety not computed."

            result["graham"] = {
                "number":           round(gn, 2),
                "eps_used":         round(eps, 2),
                "book_value_used":  round(bv, 2),
                "margin_of_safety": round(mos, 2) if mos is not None else None,
                "interpretation":   interp,
            }
        except ValueError as exc:
            result["graham_skip_reason"] = str(exc)
    else:
        missing = []
        if eps is None:
            missing.append("EPS (trailingEps)")
        if bv is None:
            missing.append("Book Value per share")
        result["graham_skip_reason"] = (
            f"Graham Number skipped — Yahoo Finance did not provide "
            f"{' and '.join(missing)} for {ticker}. "
            f"This is common for some Indian stocks and PSUs on Yahoo Finance."
        )

    # ── PE-based valuation ────────────────────────────────────────────────────
    if pe is not None and eps is not None:
        try:
            pe_result = pe_valuation(pe, eps, _DEFAULT_MARKET_PE)
            pct = pe_result["premium_discount_pct"]
            fv  = pe_result["fair_value"]

            if pct > 0:
                interp = (
                    f"At {pe:.1f}x PE, the stock trades at a {pct:.1f}% premium "
                    f"to the Nifty 50 historical average of {_DEFAULT_MARKET_PE}x. "
                    f"PE-based fair value works out to ₹{fv:.0f}. "
                    "Premium PE is normal for quality businesses — the question "
                    "is whether the quality justifies the price."
                )
            else:
                interp = (
                    f"At {pe:.1f}x PE, the stock trades at a {abs(pct):.1f}% discount "
                    f"to the Nifty 50 historical average of {_DEFAULT_MARKET_PE}x. "
                    f"PE-based fair value works out to ₹{fv:.0f}. "
                    "Lower PE can signal value — or lower growth expectations. "
                    "Worth understanding why before drawing conclusions."
                )

            result["pe_based"] = {
                **pe_result,
                "benchmark_pe":   _DEFAULT_MARKET_PE,
                "benchmark_note": (
                    f"Using Nifty 50 long-run average PE (~{_DEFAULT_MARKET_PE}x) as benchmark. "
                    "Sector averages differ significantly — IT ~25-30x, PSU Banks ~8-10x, "
                    "FMCG ~40x+. Interpret with the stock's sector in mind."
                ),
                "interpretation": interp,
            }
        except ValueError as exc:
            result["pe_skip_reason"] = str(exc)
    else:
        missing = []
        if pe is None:
            missing.append("PE ratio")
        if eps is None:
            missing.append("EPS")
        result["pe_skip_reason"] = (
            f"PE-based valuation skipped — missing {' and '.join(missing)} for {ticker}."
        )

    return result
