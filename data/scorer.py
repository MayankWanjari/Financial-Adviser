"""scorer.py — Opportunity scoring system for Indian stocks.

Scores each stock out of 100 points across 6 fundamental criteria:
  1. Value (20 pts)         — PE ratio vs market average
  2. Quality (20 pts)       — Return on Equity
  3. Safety (15 pts)        — Debt-to-Equity ratio
  4. Graham Gap (20 pts)    — Margin of safety vs Graham Number
  5. Profitability (15 pts) — Net profit margin
  6. Dividend (10 pts)      — Dividend yield

These scores surface fundamentally interesting stocks. A high score means the
numbers look attractive on these 6 metrics — it does NOT mean buy. The user decides.

All functions return dicts — no printing, no sys.exit().
"""

import time
from pathlib import Path

from data.stock_data import get_stock_snapshot
from data.valuation import graham_number, margin_of_safety

import json

_PROJECT_ROOT     = Path(__file__).parent.parent
_NIFTY50_PATH     = _PROJECT_ROOT / "config" / "nifty50.txt"
_SCORING_CFG_PATH = _PROJECT_ROOT / "config" / "scoring.json"
_FETCH_DELAY_SECS = 1.0

def load_scoring_config() -> dict:
    if not _SCORING_CFG_PATH.exists():
        raise FileNotFoundError(f"Scoring config missing: {_SCORING_CFG_PATH}")
    with open(_SCORING_CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── Grade helper ─────────────────────────────────────────────────────────────


def _grade(score: int, grades_config: dict) -> str:
    """Convert total score (0-100) to a letter grade based on config."""
    # Build list of (threshold, grade) sorted by threshold descending
    scale = [(thresh, letter) for letter, thresh in grades_config.items()]
    scale.sort(key=lambda x: x[0], reverse=True)
    
    for threshold, letter in scale:
        if score >= threshold:
            return letter
    return "F"


# ─── Config-driven scoring helpers ──────────────────────────────────────────

def _score_metric(val: float | None, metric_cfg: dict, value_formatter: callable, reverse=False) -> tuple[int, str]:
    """
    Score a generic metric based on tiers in config.
    reverse=False: higher value is better (uses threshold_min)
    reverse=True: lower value is better (uses threshold)
    """
    if val is None:
        return 0, "Data not available"
        
    for tier in metric_cfg["tiers"]:
        thresh_key = "threshold" if reverse else "threshold_min"
        thresh = tier.get(thresh_key)
        
        # null threshold is the catch-all bottom tier
        if thresh is None:
            return tier["points"], f"{value_formatter(val)} — {tier['label']}"
            
        if reverse:
            if val <= thresh:
                 return tier["points"], f"{value_formatter(val)} — {tier['label']}"
        else:
            if val >= thresh:
                 return tier["points"], f"{value_formatter(val)} — {tier['label']}"
                 
    # Fallback if tiers are malformed
    return 0, f"{value_formatter(val)} — Unclassified"


def _score_value(pe, cfg) -> tuple[int, str]:
    return _score_metric(pe, cfg, lambda v: f"PE {v:.1f}x", reverse=True)

def _score_quality(roe, cfg) -> tuple[int, str]:
    return _score_metric(roe, cfg, lambda v: f"ROE {v*100:.1f}%")

def _score_safety(de, cfg) -> tuple[int, str]:
    return _score_metric(de, cfg, lambda v: f"D/E {v:.2f}x", reverse=True)

def _score_graham_gap(eps, book_value, price, cfg) -> tuple[int, str]:
    if eps is None or book_value is None or price is None:
        return 0, "Graham Number not calculable (missing data)"
    try:
        gn  = graham_number(eps, book_value)
        mos = margin_of_safety(price, gn)
    except ValueError:
        return 0, "Graham Number not calculable (negative EPS/BV)"
        
    pts, msg = _score_metric(mos, cfg, lambda v: f"{v:+.1f}% vs Graham Number ₹{gn:.0f}")
    return pts, msg

def _score_profitability(net_margin, cfg) -> tuple[int, str]:
    return _score_metric(net_margin, cfg, lambda v: f"Net margin {v*100:.1f}%")

def _score_dividend(div_yield, cfg) -> tuple[int, str]:
    # yfinance div_yield is already %.
    if div_yield == 0:
        return 0, "No dividend paid"
    return _score_metric(div_yield, cfg, lambda v: f"Yield {v:.2f}%")


# ─── Interpretation helper ────────────────────────────────────────────────────


def _generate_interpretation(breakdown: dict, data: dict) -> str:
    """
    Generate a one-line plain-English summary of the score result.

    Finds the strongest and weakest criteria (relative to their max points)
    and writes a sentence that captures the key take-away.
    """
    criteria = [
        ("value",         breakdown["value"]["score"],         20, "low PE"),
        ("quality",       breakdown["quality"]["score"],       20, "high ROE"),
        ("safety",        breakdown["safety"]["score"],        15, "low debt"),
        ("graham_gap",    breakdown["graham_gap"]["score"],    20, "Graham value"),
        ("profitability", breakdown["profitability"]["score"], 15, "strong margins"),
        ("dividend",      breakdown["dividend"]["score"],      10, "dividend income"),
    ]

    # Sort by score ratio (score / max) so we compare fairly across different maxes
    by_ratio = sorted(criteria, key=lambda x: x[1] / x[2], reverse=True)
    strongest_label = by_ratio[0][3]
    weakest_label   = by_ratio[-1][3]

    total = sum(c[1] for c in criteria)

    if total >= 70:
        return f"Strong fundamentals — standout strength: {strongest_label}"
    if total >= 50:
        return f"Decent fundamentals — strength in {strongest_label}, weakness in {weakest_label}"
    if total >= 35:
        return f"Mixed picture — some merit in {strongest_label} but notable weakness in {weakest_label}"
    return f"Weak fundamentals on most criteria — especially poor: {weakest_label}"


# ─── Main public functions ────────────────────────────────────────────────────


def score_stock(ticker: str) -> dict:
    """
    Score a stock's fundamental attractiveness out of 100 points.

    Fetches live data via get_stock_snapshot() and scores 6 criteria:
    value (PE), quality (ROE), safety (D/E), Graham gap, profitability, dividend.

    Args:
        ticker: NSE ticker symbol without .NS suffix, e.g. 'RELIANCE'.

    Returns:
        A dict with:
            ticker         (str)  — symbol
            name           (str)  — company name
            total_score    (int)  — 0 to 100
            grade          (str)  — A / B / C / D / F
            breakdown      (dict) — six criteria, each {score, max, detail}
            raw_data       (dict) — full get_stock_snapshot() result
            interpretation (str)  — one-line plain-English summary

    Raises:
        ValueError:      If ticker not found on Yahoo Finance.
        ConnectionError: If Yahoo Finance cannot be reached.
    """
    data = get_stock_snapshot(ticker)
    
    cfg = load_scoring_config()

    pe         = data.get("pe_trailing")
    roe        = data.get("roe")
    de         = data.get("de_ratio")
    eps        = data.get("eps_trailing")
    bv         = data.get("book_value")
    price      = data.get("current_price")
    net_margin = data.get("net_margin")
    div_yield  = data.get("div_yield")

    v_score, v_detail = _score_value(pe, cfg["value"])
    q_score, q_detail = _score_quality(roe, cfg["quality"])
    s_score, s_detail = _score_safety(de, cfg["safety"])
    g_score, g_detail = _score_graham_gap(eps, bv, price, cfg["graham_gap"])
    p_score, p_detail = _score_profitability(net_margin, cfg["profitability"])
    d_score, d_detail = _score_dividend(div_yield, cfg["dividend"])

    total = v_score + q_score + s_score + g_score + p_score + d_score

    breakdown = {
        "value":         {"score": v_score, "max": cfg["value"]["max_points"], "detail": v_detail},
        "quality":       {"score": q_score, "max": cfg["quality"]["max_points"], "detail": q_detail},
        "safety":        {"score": s_score, "max": cfg["safety"]["max_points"], "detail": s_detail},
        "graham_gap":    {"score": g_score, "max": cfg["graham_gap"]["max_points"], "detail": g_detail},
        "profitability": {"score": p_score, "max": cfg["profitability"]["max_points"], "detail": p_detail},
        "dividend":      {"score": d_score, "max": cfg["dividend"]["max_points"], "detail": d_detail},
    }

    return {
        "ticker":          data["symbol"],
        "name":            data["name"],
        "total_score":     total,
        "grade":           _grade(total, cfg["grades"]),
        "breakdown":       breakdown,
        "raw_data":        data,
        "interpretation":  _generate_interpretation(breakdown, data),
    }


def find_opportunities(universe: str = "nifty50", on_progress=None) -> tuple[list[dict], list[str]]:
    """
    Score all Nifty 50 stocks and return them ranked by total score.

    Fetches each stock with a 1-second delay between calls to avoid Yahoo Finance
    rate-limiting. With ~50 stocks this takes roughly 2-3 minutes.
    Stocks that fail to fetch are skipped.

    Args:
        universe: Universe to scan. Currently only 'nifty50' is supported.
        on_progress: Optional callback function with signature (current, total, ticker)

    Returns:
        (scored, failed) where:
            scored is a List of score_stock() result dicts, sorted by total_score descending.
            failed is a list of tickers that failed to fetch.

    Raises:
        FileNotFoundError: If config/nifty50.txt doesn't exist.
        ValueError: If config/nifty50.txt is empty.
    """
    if not _NIFTY50_PATH.exists():
        raise FileNotFoundError(
            f"Nifty 50 ticker list not found: {_NIFTY50_PATH}\n"
            "Expected config/nifty50.txt with one NSE ticker per line."
        )

    tickers = [
        line.strip().upper()
        for line in _NIFTY50_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    if not tickers:
        raise ValueError("config/nifty50.txt is empty — cannot scan opportunities.")

    scored: list[dict] = []
    failed: list[str] = []
    total = len(tickers)

    for i, ticker in enumerate(tickers, start=1):
        if on_progress:
            on_progress(i, total, ticker)
            
        try:
            result = score_stock(ticker)
            scored.append(result)
        except Exception:
            failed.append(ticker) # Track failed tickers

        if i < total:
            time.sleep(_FETCH_DELAY_SECS)

    # Highest score first
    scored.sort(key=lambda x: x["total_score"], reverse=True)
    return scored, failed
