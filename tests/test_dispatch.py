"""Tests for agent/dispatch.py — pure helper functions only (no network calls)."""

import pytest
from agent.dispatch import _validate_ticker


# ─── _validate_ticker ─────────────────────────────────────────────────────────

def test_validate_standard_tickers():
    """Common NSE tickers should pass validation and come back uppercased."""
    assert _validate_ticker("RELIANCE")  == "RELIANCE"
    assert _validate_ticker("TCS")       == "TCS"
    assert _validate_ticker("HDFCBANK")  == "HDFCBANK"
    assert _validate_ticker("INFY")      == "INFY"


def test_validate_lowercases_are_accepted():
    """Lowercase input should be normalised to uppercase."""
    assert _validate_ticker("reliance") == "RELIANCE"
    assert _validate_ticker("tcs")      == "TCS"


def test_validate_strips_whitespace():
    """Leading/trailing whitespace should be stripped before validation."""
    assert _validate_ticker("  RELIANCE  ") == "RELIANCE"
    assert _validate_ticker("\tTCS\n")       == "TCS"


def test_validate_special_char_tickers():
    """NSE tickers with '&' (M&M) and '-' (BAJAJ-AUTO) should pass."""
    assert _validate_ticker("M&M")       == "M&M"
    assert _validate_ticker("BAJAJ-AUTO") == "BAJAJ-AUTO"


def test_validate_numeric_in_ticker():
    """Tickers that include digits should pass."""
    assert _validate_ticker("3MINDIA") == "3MINDIA"


def test_validate_rejects_empty_string():
    """An empty string (or whitespace-only) should raise ValueError."""
    with pytest.raises(ValueError, match="empty"):
        _validate_ticker("")

    with pytest.raises(ValueError, match="empty"):
        _validate_ticker("   ")


def test_validate_rejects_newline_injection():
    """A ticker with an embedded newline should be rejected — it could corrupt watchlist.txt."""
    with pytest.raises(ValueError):
        _validate_ticker("RELIANCE\nMALICIOUS")


def test_validate_rejects_semicolon():
    """Semicolons and shell-special chars should be rejected."""
    with pytest.raises(ValueError):
        _validate_ticker("TCS; rm -rf /")


def test_validate_rejects_slash():
    """Forward slashes are not valid in NSE ticker symbols."""
    with pytest.raises(ValueError):
        _validate_ticker("TCS/INFY")


def test_validate_rejects_too_long():
    """Strings over 25 characters should be rejected as obviously not a real ticker."""
    with pytest.raises(ValueError):
        _validate_ticker("A" * 26)


def test_validate_max_length_passes():
    """25-character strings of valid chars should pass."""
    ticker = "A" * 25
    assert _validate_ticker(ticker) == ticker
