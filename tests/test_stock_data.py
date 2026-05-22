"""Tests for stock_data.py"""

import pytest
from data.stock_data import (
    _indian_number_format,
    fmt_crore,
    fmt_price,
    fmt_pct,
    fmt_ratio,
    fmt_div_yield
)

def test_indian_number_format_small():
    assert _indian_number_format(500) == "500"

def test_indian_number_format_large():
    assert _indian_number_format(19254000) == "1,92,54,000"
    assert _indian_number_format(1925400) == "19,25,400"

def test_fmt_crore():
    assert fmt_crore(1_00_00_000) == "₹1 Cr"
    assert fmt_crore(15_50_00_000) == "₹16 Cr" # Rounds to nearest int before formatting
    assert fmt_crore(None) == "N/A"

def test_fmt_price():
    assert fmt_price(1234.567) == "₹1,234.57"
    assert fmt_price(None) == "N/A"

def test_fmt_pct():
    assert fmt_pct(0.092) == "9.20%"
    assert fmt_pct(None) == "N/A"

def test_fmt_ratio():
    assert fmt_ratio(15.432) == "15.43"
    assert fmt_ratio(15.432, decimals=1) == "15.4"
    assert fmt_ratio(None) == "N/A"

def test_fmt_div_yield():
    assert fmt_div_yield(0.40) == "0.40%"
    assert fmt_div_yield(None) == "N/A"

def test_fmt_div_yield_warning():
    result = fmt_div_yield(30.0)
    assert "30.00%" in result
    assert "verify - unusually high" in result
