"""portfolio.py — Personal stock portfolio tracker.

Stores the user's actual holdings (ticker, quantity, average buy price) in
config/portfolio.json and computes unrealized P&L against live prices.

All functions return dicts or strings — no printing, no sys.exit().
config/portfolio.json is gitignored so personal financial data stays local.
"""

import json
from datetime import datetime
from pathlib import Path

from data.stock_data import get_stock_snapshot
from data.scorer import score_stock

_PROJECT_ROOT   = Path(__file__).parent.parent
_PORTFOLIO_PATH = _PROJECT_ROOT / "config" / "portfolio.json"

_EMPTY_PORTFOLIO = {"holdings": [], "last_updated": None}


# ─── File I/O ─────────────────────────────────────────────────────────────────


def load_portfolio() -> dict:
    """
    Read config/portfolio.json and return the portfolio dict.

    Creates the file with an empty portfolio if it doesn't exist yet, so the
    user never has to create it manually.

    Returns:
        Dict with keys 'holdings' (list) and 'last_updated' (str | None).
    """
    if not _PORTFOLIO_PATH.exists():
        save_portfolio(_EMPTY_PORTFOLIO.copy())
        return _EMPTY_PORTFOLIO.copy()

    try:
        return json.loads(_PORTFOLIO_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        # Corrupt or unreadable file — start fresh rather than crashing
        return _EMPTY_PORTFOLIO.copy()


def save_portfolio(portfolio: dict) -> None:
    """
    Write the portfolio dict to config/portfolio.json.

    Automatically stamps the 'last_updated' field with the current datetime.

    Args:
        portfolio: Dict with at least a 'holdings' key.
    """
    portfolio["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    _PORTFOLIO_PATH.write_text(
        json.dumps(portfolio, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ─── Holdings management ──────────────────────────────────────────────────────


def add_holding(ticker: str, quantity: int, avg_price: float) -> str:
    """
    Add a stock holding to the portfolio, or update it if it already exists.

    If the ticker is already in the portfolio, the two lots are merged using a
    weighted average price so the cost basis stays accurate:
        new_avg = (old_qty × old_price + new_qty × new_price) / (old_qty + new_qty)

    Args:
        ticker:    NSE ticker symbol (will be uppercased), e.g. 'RELIANCE'.
        quantity:  Number of shares added (must be positive).
        avg_price: Average purchase price per share in ₹ (must be positive).

    Returns:
        A plain-English confirmation message.

    Raises:
        ValueError: If quantity or avg_price is not positive.
    """
    ticker = ticker.strip().upper()
    if quantity <= 0:
        raise ValueError(f"Quantity must be positive, got {quantity}.")
    if avg_price <= 0:
        raise ValueError(f"Avg price must be positive, got {avg_price}.")

    portfolio = load_portfolio()
    holdings  = portfolio["holdings"]

    for holding in holdings:
        if holding["ticker"] == ticker:
            # Merge with existing lot using weighted average
            old_qty   = holding["quantity"]
            old_price = holding["avg_price"]
            new_qty   = old_qty + quantity
            new_price = (old_qty * old_price + quantity * avg_price) / new_qty

            holding["quantity"]  = new_qty
            holding["avg_price"] = round(new_price, 2)

            save_portfolio(portfolio)
            return (
                f"{ticker} updated: {new_qty} shares at weighted avg ₹{new_price:,.2f}. "
                f"(Added {quantity} shares to existing {old_qty} at ₹{old_price:,.2f}.)"
            )

    # New holding — append
    holdings.append({
        "ticker":     ticker,
        "quantity":   quantity,
        "avg_price":  round(avg_price, 2),
        "date_added": datetime.now().strftime("%Y-%m-%d"),
    })
    save_portfolio(portfolio)
    return (
        f"{ticker} added to portfolio: {quantity} shares at ₹{avg_price:,.2f}. "
        f"Total invested: ₹{quantity * avg_price:,.2f}."
    )


def remove_holding(ticker: str) -> str:
    """
    Remove a holding from the portfolio completely.

    Args:
        ticker: NSE ticker symbol (case-insensitive).

    Returns:
        A plain-English confirmation or "not found" message.
    """
    ticker    = ticker.strip().upper()
    portfolio = load_portfolio()
    holdings  = portfolio["holdings"]

    before = len(holdings)
    portfolio["holdings"] = [h for h in holdings if h["ticker"] != ticker]

    if len(portfolio["holdings"]) == before:
        return f"{ticker} was not found in your portfolio."

    save_portfolio(portfolio)
    return f"{ticker} removed from your portfolio."


# ─── Portfolio summary with live data ─────────────────────────────────────────


def portfolio_summary() -> dict:
    """
    Compute a full portfolio snapshot with live prices and P&L.

    For each holding: fetches the current price via get_stock_snapshot() and
    scores it via score_stock(). Calculates invested amount, current value,
    and unrealized P&L (absolute and percentage).

    Returns:
        A dict with:
            holdings  (list)  — each item is the original holding dict enriched with:
                                  name, current_price, invested_amount, current_value,
                                  pnl_amount, pnl_pct, score, grade, sector
                                  (fields are None if data fetch failed)
            totals    (dict)  — total_invested, total_current_value, total_pnl,
                                  total_pnl_pct (all in ₹, pct as float)
            top_gainer (dict | None) — holding with highest pnl_pct
            top_loser  (dict | None) — holding with lowest pnl_pct

    Raises:
        ValueError: If the portfolio file is empty (no holdings).
    """
    portfolio = load_portfolio()
    raw_holdings = portfolio.get("holdings", [])

    if not raw_holdings:
        raise ValueError(
            "Your portfolio is empty. "
            "Add holdings first: e.g. 'Add 10 RELIANCE shares at ₹2450'."
        )

    enriched = []

    for holding in raw_holdings:
        ticker   = holding["ticker"]
        qty      = holding["quantity"]
        avg_px   = holding["avg_price"]
        invested = qty * avg_px

        entry: dict = {
            **holding,
            "invested_amount": round(invested, 2),
            # Filled below if data fetch succeeds, else None
            "name":          None,
            "current_price": None,
            "current_value": None,
            "pnl_amount":    None,
            "pnl_pct":       None,
            "score":         None,
            "grade":         None,
            "sector":        None,
        }

        try:
            stock = get_stock_snapshot(ticker)
            price = stock.get("current_price")

            if price is not None:
                cur_val  = qty * price
                pnl_amt  = cur_val - invested
                pnl_pct  = (pnl_amt / invested) * 100

                entry["name"]          = stock.get("name")
                entry["current_price"] = round(price, 2)
                entry["current_value"] = round(cur_val, 2)
                entry["pnl_amount"]    = round(pnl_amt, 2)
                entry["pnl_pct"]       = round(pnl_pct, 2)
                entry["sector"]        = stock.get("sector")
        except Exception:
            pass  # Leave fields as None — agent will show N/A

        try:
            scored = score_stock(ticker)
            entry["score"] = scored["total_score"]
            entry["grade"] = scored["grade"]
        except Exception:
            pass

        enriched.append(entry)

    # ── Aggregate totals (only for holdings where we have live data) ───────────
    total_invested = sum(h["invested_amount"] for h in enriched)

    valued = [h for h in enriched if h["current_value"] is not None]
    total_current  = sum(h["current_value"] for h in valued) if valued else None
    total_pnl      = (total_current - sum(h["invested_amount"] for h in valued)) if valued else None
    total_pnl_pct  = (total_pnl / sum(h["invested_amount"] for h in valued) * 100) if valued else None

    totals = {
        "total_invested":      round(total_invested, 2),
        "total_current_value": round(total_current, 2) if total_current is not None else None,
        "total_pnl":           round(total_pnl, 2)     if total_pnl is not None else None,
        "total_pnl_pct":       round(total_pnl_pct, 2) if total_pnl_pct is not None else None,
    }

    # ── Top gainer and loser (among holdings with live P&L data) ──────────────
    pnl_holdings  = [h for h in enriched if h["pnl_pct"] is not None]
    top_gainer = max(pnl_holdings, key=lambda h: h["pnl_pct"]) if pnl_holdings else None
    top_loser  = min(pnl_holdings, key=lambda h: h["pnl_pct"]) if pnl_holdings else None

    return {
        "holdings":   enriched,
        "totals":     totals,
        "top_gainer": top_gainer,
        "top_loser":  top_loser,
    }
