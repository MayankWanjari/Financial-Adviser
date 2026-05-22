"""Tests for valuation.py"""

import math
import pytest
from data.valuation import graham_number, margin_of_safety, pe_valuation

def test_graham_number_basic():
    # sqrt(22.5 * 100 * 50) = sqrt(112500) = ~335.41
    expected = math.sqrt(22.5 * 100 * 50)
    assert graham_number(100, 50) == pytest.approx(expected)

def test_graham_number_negative_eps_raises():
    with pytest.raises(ValueError, match="positive EPS"):
        graham_number(-10, 50)

def test_graham_number_negative_book_value_raises():
    with pytest.raises(ValueError, match="positive EPS"):
        graham_number(10, -50)

def test_graham_number_zero_raises():
    with pytest.raises(ValueError):
        graham_number(0, 50)

def test_margin_of_safety_undervalued():
    # Price is 750, intrinsic value is 1000. Gap is 250, which is 25% of 1000.
    mos = margin_of_safety(750, 1000)
    assert mos == pytest.approx(25.0)

def test_margin_of_safety_overvalued():
    # Price is 1200, intrinsic value is 1000. Gap is -200, which is -20% of 1000.
    mos = margin_of_safety(1200, 1000)
    assert mos == pytest.approx(-20.0)

def test_margin_of_safety_fairly_valued():
    mos = margin_of_safety(1000, 1000)
    assert mos == pytest.approx(0.0)

def test_margin_of_safety_zero_intrinsic_raises():
    with pytest.raises(ValueError, match="cannot be zero"):
        margin_of_safety(100, 0)

def test_pe_valuation_basic():
    # Sector avg PE is 20, EPS is 50. Fair value = 1000.
    # Current PE is 25. Premium is (25 - 20) / 20 * 100 = 25%.
    result = pe_valuation(current_pe=25.0, eps=50.0, sector_avg_pe=20.0)
    
    assert result["fair_value"] == pytest.approx(1000.0)
    assert result["premium_discount_pct"] == pytest.approx(25.0)
    assert result["current_pe"] == 25.0
    assert result["sector_avg_pe"] == 20.0

def test_pe_valuation_discount():
    # Current PE is 15, Sector PE is 20.
    # Discount is (15 - 20) / 20 * 100 = -25%.
    result = pe_valuation(current_pe=15.0, eps=50.0, sector_avg_pe=20.0)
    assert result["premium_discount_pct"] == pytest.approx(-25.0)

def test_pe_valuation_negative_eps_raises():
    with pytest.raises(ValueError, match="positive EPS"):
        pe_valuation(current_pe=15.0, eps=-10.0, sector_avg_pe=20.0)

def test_pe_valuation_negative_sector_pe_raises():
    with pytest.raises(ValueError, match="must be positive"):
        pe_valuation(current_pe=15.0, eps=50.0, sector_avg_pe=-5.0)
