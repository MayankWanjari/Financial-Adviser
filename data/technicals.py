"""
data/technicals.py — Basic technical indicator analysis for Indian stocks.

Calculates moving averages (50/200-day SMA), RSI (14-day), trend signals,
golden/death cross detection, and support/resistance levels from 1-year price history.

All functions return dicts — no printing, no sys.exit().
"""

import yfinance as yf

from data.cache import cache_get, cache_set

# Cache technical indicators for 15 minutes — same cadence as stock snapshots
_TECH_TTL = 900


# ─── Pure computation helpers (testable without network) ──────────────────────

def _calculate_rsi(closes: list[float], period: int = 14) -> float | None:
    """
    Calculate RSI using Wilder's smoothing method.

    Args:
        closes: List of closing prices ordered oldest → newest.
        period: Look-back period, default 14.

    Returns:
        RSI value rounded to 2 decimal places, or None if too few data points.
    """
    n = len(closes)
    if n < period + 1:
        return None

    changes = [closes[i] - closes[i - 1] for i in range(1, n)]
    gains   = [max(c, 0.0) for c in changes]
    losses  = [abs(min(c, 0.0)) for c in changes]

    # Seed: simple average of the first `period` up/down moves
    avg_gain = sum(gains[:period])  / period
    avg_loss = sum(losses[:period]) / period

    # Wilder exponential smoothing for the rest
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i])  / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def _get_trend_signal(
    price: float,
    sma50: float | None,
    sma200: float | None,
) -> str:
    """
    Determine trend signal from price position relative to moving averages.

    Returns one of: 'Bullish (strong uptrend)', 'Neutral (pulling back in uptrend)',
    'Bearish (strong downtrend)', 'Mixed', 'Bullish', 'Bearish', or 'N/A'.
    """
    if sma50 is not None and sma200 is not None:
        if price > sma50 and sma50 > sma200:
            return "Bullish (strong uptrend)"
        if sma50 > price and price > sma200:
            return "Neutral (pulling back in uptrend)"
        if price < sma50 and sma50 < sma200:
            return "Bearish (strong downtrend)"
        return "Mixed"
    if sma50 is not None:
        return "Bullish" if price > sma50 else "Bearish"
    return "N/A"


def get_technical_indicators(ticker: str) -> dict:
    """
    Compute basic technical indicators for an NSE stock using 1-year daily prices.

    Indicators calculated:
        - 50-day and 200-day Simple Moving Average (SMA)
        - Trend signal based on price vs both MAs
        - Golden Cross (SMA50 crossed above SMA200 in last 30 trading days)
        - Death Cross (SMA50 crossed below SMA200 in last 30 trading days)
        - 14-day RSI using standard Wilder smoothing
        - 20-day support (lowest low) and resistance (highest high)

    Args:
        ticker: NSE ticker without .NS suffix, e.g. 'RELIANCE'.

    Returns:
        A dict with:
            ticker          (str)
            name            (str)
            current_price   (float)
            sma50           (float | None)  — 50-day SMA; None if < 50 data points
            sma200          (float | None)  — 200-day SMA; None if < 200 data points
            price_vs_sma50  (str)           — "above" / "below" / "N/A"
            price_vs_sma200 (str)           — "above" / "below" / "N/A"
            trend_signal    (str)           — Bullish / Bearish / Neutral / Mixed / N/A
            golden_cross    (bool)          — SMA50 crossed above SMA200 in last 30 days
            death_cross     (bool)          — SMA50 crossed below SMA200 in last 30 days
            rsi             (float | None)  — 14-day RSI; None if insufficient data
            rsi_signal      (str)           — "Overbought" / "Oversold" / "Neutral" / "N/A"
            support         (float)         — lowest close in last 20 trading days
            resistance      (float)         — highest close in last 20 trading days
            interpretation  (str)           — one-line plain-English summary

    Raises:
        ValueError:      If ticker not found or price history too short.
        ConnectionError: If Yahoo Finance cannot be reached.
    """
    ticker = ticker.strip().upper()

    cache_key = f"technicals_{ticker}"
    cached = cache_get(cache_key, _TECH_TTL)
    if cached is not None:
        return cached

    full_ticker = f"{ticker}.NS"

    # ── Fetch info (name + current price) ────────────────────────────────────
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

    current_price = (
        info.get("currentPrice")
        or info.get("regularMarketPrice")
        or info.get("previousClose")
    )
    if not current_price:
        raise ValueError(f"Could not fetch current price for {ticker}.")

    # ── Fetch 1-year daily price history ─────────────────────────────────────
    try:
        hist = stock.history(period="1y")
    except Exception as e:
        raise ConnectionError(
            f"Could not fetch price history for '{full_ticker}'. Detail: {e}"
        ) from e

    if hist.empty or len(hist) < 20:
        raise ValueError(
            f"Not enough price history for {ticker} "
            f"(got {len(hist)} data points, need at least 20). "
            f"Try checking the ticker symbol."
        )

    closes = hist["Close"].dropna().tolist()
    n = len(closes)

    # ── Simple Moving Averages ────────────────────────────────────────────────
    # SMA = average of the last N closing prices.
    # We only compute if we have enough data points.
    sma50: float | None  = round(sum(closes[-50:])  / 50,  2) if n >= 50  else None
    sma200: float | None = round(sum(closes[-200:]) / 200, 2) if n >= 200 else None

    # ── Price vs MAs ─────────────────────────────────────────────────────────
    price_vs_sma50  = "N/A"
    price_vs_sma200 = "N/A"
    if sma50 is not None:
        price_vs_sma50  = "above" if current_price > sma50  else "below"
    if sma200 is not None:
        price_vs_sma200 = "above" if current_price > sma200 else "below"

    # ── Trend signal ──────────────────────────────────────────────────────────
    trend_signal = _get_trend_signal(current_price, sma50, sma200)

    # ── Golden Cross / Death Cross detection ──────────────────────────────────
    # A golden cross is when the 50-day SMA crosses ABOVE the 200-day SMA.
    # A death cross is when the 50-day SMA crosses BELOW the 200-day SMA.
    # We check if the crossover happened in the last 30 trading days.
    golden_cross = False
    death_cross  = False

    if n >= 201:
        # Look at the last 30+1 days to detect a recent crossover
        check_window = min(31, n - 200)
        prev_sma50_above  = None  # Whether SMA50 was above SMA200 at the start of the window

        for i in range(check_window, 0, -1):
            # i steps back from the end; compute 50/200 SMAs at that historical point
            end_idx = n - i
            if end_idx < 200:
                continue
            s50  = sum(closes[end_idx - 50:end_idx])  / 50
            s200 = sum(closes[end_idx - 200:end_idx]) / 200
            currently_above = s50 > s200

            if prev_sma50_above is None:
                prev_sma50_above = currently_above
            else:
                # Detect direction flip
                if not prev_sma50_above and currently_above:
                    golden_cross = True
                elif prev_sma50_above and not currently_above:
                    death_cross = True
                prev_sma50_above = currently_above

    # ── RSI (14-day) ─────────────────────────────────────────────────────────
    rsi_signal = "N/A"
    rsi = _calculate_rsi(closes)
    if rsi is not None:
        if rsi > 70:
            rsi_signal = "Overbought"
        elif rsi < 30:
            rsi_signal = "Oversold"
        else:
            rsi_signal = "Neutral"

    # ── Support and Resistance ────────────────────────────────────────────────
    # Simple definition: support = lowest close in last 20 days,
    # resistance = highest close in last 20 days.
    last_20 = closes[-20:]
    support    = round(min(last_20), 2)
    resistance = round(max(last_20), 2)

    # ── One-line interpretation ───────────────────────────────────────────────
    parts = []
    if trend_signal not in ("N/A", "Mixed"):
        parts.append(trend_signal)
    if rsi_signal != "N/A":
        parts.append(f"RSI {rsi:.1f} ({rsi_signal})" if rsi is not None else "RSI N/A")
    if golden_cross:
        parts.append("Golden Cross recently (bullish MA crossover)")
    if death_cross:
        parts.append("Death Cross recently (bearish MA crossover)")

    if parts:
        interpretation = f"{ticker}: {' | '.join(parts)}."
    else:
        interpretation = f"{ticker}: Insufficient data for a full technical read."

    result = {
        "ticker":           ticker,
        "name":             name,
        "current_price":    round(float(current_price), 2),
        "sma50":            sma50,
        "sma200":           sma200,
        "price_vs_sma50":   price_vs_sma50,
        "price_vs_sma200":  price_vs_sma200,
        "trend_signal":     trend_signal,
        "golden_cross":     golden_cross,
        "death_cross":      death_cross,
        "rsi":              rsi,
        "rsi_signal":       rsi_signal,
        "support":          support,
        "resistance":       resistance,
        "interpretation":   interpretation,
    }

    cache_set(cache_key, result)
    return result
