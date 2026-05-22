"""Tests for data/dividends.py pure helpers — no network calls."""

from data.dividends import _calculate_cagr, _classify_consistency


# ── _calculate_cagr ───────────────────────────────────────────────────────────

def test_cagr_positive_growth():
    # 100 → 121 in 2 years = exactly 10% CAGR
    cagr = _calculate_cagr(100.0, 121.0, 2)
    assert cagr is not None
    assert abs(cagr - 0.10) < 0.001


def test_cagr_zero_growth():
    cagr = _calculate_cagr(100.0, 100.0, 3)
    assert cagr == 0.0


def test_cagr_negative_growth():
    cagr = _calculate_cagr(100.0, 50.0, 1)
    assert cagr == -0.5


def test_cagr_returns_none_if_earliest_zero():
    assert _calculate_cagr(0.0, 100.0, 3) is None


def test_cagr_returns_none_if_earliest_negative():
    assert _calculate_cagr(-10.0, 100.0, 3) is None


def test_cagr_returns_none_if_latest_zero():
    assert _calculate_cagr(100.0, 0.0, 3) is None


def test_cagr_returns_none_if_n_zero():
    assert _calculate_cagr(100.0, 100.0, 0) is None


def test_cagr_returns_none_if_n_negative():
    assert _calculate_cagr(100.0, 100.0, -1) is None


def test_cagr_result_is_float():
    result = _calculate_cagr(10.0, 20.0, 2)
    assert isinstance(result, float)


# ── _classify_consistency ─────────────────────────────────────────────────────

def test_consistency_growing():
    annual = {2021: 5.0, 2022: 6.0, 2023: 7.0}
    assert _classify_consistency(annual, 2020, 2023) == "Growing"


def test_consistency_consistent_not_growing():
    # Paid every year but one year dipped
    annual = {2021: 5.0, 2022: 7.0, 2023: 6.0}
    assert _classify_consistency(annual, 2020, 2023) == "Consistent"


def test_consistency_consistent_flat():
    annual = {2021: 5.0, 2022: 5.0, 2023: 5.0}
    assert _classify_consistency(annual, 2020, 2023) == "Growing"  # non-decreasing → Growing


def test_consistency_irregular_missing_year():
    annual = {2021: 5.0, 2023: 7.0}  # 2022 missing
    assert _classify_consistency(annual, 2020, 2023) == "Irregular"


def test_consistency_irregular_empty_dict():
    assert _classify_consistency({}, 2020, 2023) == "Irregular"


def test_consistency_single_year_is_growing():
    # Only 1 year expected → trivially non-decreasing → Growing
    annual = {2023: 10.0}
    result = _classify_consistency(annual, 2022, 2023)
    assert result in ("Growing", "Consistent")
