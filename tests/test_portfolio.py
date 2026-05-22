"""Tests for data/portfolio.py — uses temp_portfolio fixture from conftest.py.

The conftest.py fixture pre-writes an empty portfolio.json before each test,
guaranteeing a clean slate regardless of what's in config/portfolio.json.
"""

import json
import pytest

from data.portfolio import load_portfolio, add_holding, remove_holding, save_portfolio


# ─── load_portfolio ───────────────────────────────────────────────────────────

def test_load_returns_empty_when_file_is_empty(temp_portfolio):
    """The conftest fixture pre-populates an empty portfolio; load should return it."""
    portfolio = load_portfolio()
    assert portfolio["holdings"] == []


def test_load_reads_existing_file(temp_portfolio):
    data = {"holdings": [{"ticker": "TCS", "quantity": 5, "avg_price": 4000.0}], "last_updated": None}
    temp_portfolio.write_text(json.dumps(data), encoding="utf-8")
    portfolio = load_portfolio()
    assert len(portfolio["holdings"]) == 1
    assert portfolio["holdings"][0]["ticker"] == "TCS"


def test_load_corrupt_file_returns_empty(temp_portfolio):
    temp_portfolio.write_text("not valid json {{{", encoding="utf-8")
    assert load_portfolio()["holdings"] == []


# ─── add_holding ──────────────────────────────────────────────────────────────

def test_add_new_holding(temp_portfolio):
    msg = add_holding("RELIANCE", quantity=10, avg_price=2500.0)
    assert "RELIANCE" in msg
    portfolio = load_portfolio()
    assert len(portfolio["holdings"]) == 1
    h = portfolio["holdings"][0]
    assert h["ticker"] == "RELIANCE"
    assert h["quantity"] == 10
    assert h["avg_price"] == 2500.0


def test_add_holding_weighted_average(temp_portfolio):
    """Adding to an existing holding must compute a weighted average price — not duplicate."""
    add_holding("TCS", quantity=5, avg_price=4000.0)
    add_holding("TCS", quantity=5, avg_price=3000.0)

    portfolio = load_portfolio()
    assert len(portfolio["holdings"]) == 1          # merged, not duplicated
    h = portfolio["holdings"][0]
    assert h["quantity"] == 10
    assert h["avg_price"] == 3500.0                 # (5×4000 + 5×3000) / 10


def test_add_multiple_different_tickers(temp_portfolio):
    add_holding("TCS",  quantity=5,  avg_price=4000.0)
    add_holding("INFY", quantity=10, avg_price=1500.0)

    portfolio = load_portfolio()
    tickers = [h["ticker"] for h in portfolio["holdings"]]
    assert "TCS"  in tickers
    assert "INFY" in tickers
    assert len(portfolio["holdings"]) == 2


def test_add_holding_normalises_ticker(temp_portfolio):
    add_holding("reliance", quantity=5, avg_price=2500.0)
    assert load_portfolio()["holdings"][0]["ticker"] == "RELIANCE"


def test_add_holding_rejects_zero_quantity(temp_portfolio):
    with pytest.raises(ValueError, match="Quantity"):
        add_holding("TCS", quantity=0, avg_price=4000.0)


def test_add_holding_rejects_negative_quantity(temp_portfolio):
    with pytest.raises(ValueError, match="Quantity"):
        add_holding("TCS", quantity=-5, avg_price=4000.0)


def test_add_holding_rejects_zero_price(temp_portfolio):
    with pytest.raises(ValueError, match="price"):
        add_holding("TCS", quantity=5, avg_price=0.0)


def test_add_holding_rejects_negative_price(temp_portfolio):
    with pytest.raises(ValueError, match="price"):
        add_holding("TCS", quantity=5, avg_price=-100.0)


# ─── remove_holding ───────────────────────────────────────────────────────────

def test_remove_existing_holding(temp_portfolio):
    add_holding("INFY", quantity=10, avg_price=1500.0)
    msg = remove_holding("INFY")
    assert "removed" in msg.lower()
    assert len(load_portfolio()["holdings"]) == 0   # back to empty


def test_remove_nonexistent_holding(temp_portfolio):
    assert "not found" in remove_holding("WIPRO").lower()


def test_remove_leaves_other_holdings_intact(temp_portfolio):
    add_holding("TCS",  quantity=5, avg_price=4000.0)
    add_holding("INFY", quantity=5, avg_price=1500.0)
    remove_holding("TCS")
    tickers = [h["ticker"] for h in load_portfolio()["holdings"]]
    assert "INFY" in tickers
    assert "TCS"  not in tickers


# ─── save_portfolio ───────────────────────────────────────────────────────────

def test_save_stamps_last_updated(temp_portfolio):
    save_portfolio({"holdings": []})
    assert load_portfolio().get("last_updated") is not None
