"""Tests for data/pe_bands.py pure helpers — no network calls."""

from data.pe_bands import _pe_position_label


def test_position_cheap_when_below_25th():
    assert _pe_position_label(10.0, 15.0, 25.0, 35.0) == "cheap"


def test_position_fair_between_25th_and_median():
    assert _pe_position_label(20.0, 15.0, 25.0, 35.0) == "fair"


def test_position_expensive_between_median_and_75th():
    assert _pe_position_label(30.0, 15.0, 25.0, 35.0) == "expensive"


def test_position_very_expensive_above_75th():
    assert _pe_position_label(40.0, 15.0, 25.0, 35.0) == "very_expensive"


def test_position_unknown_when_current_pe_none():
    assert _pe_position_label(None, 15.0, 25.0, 35.0) == "unknown"


def test_position_boundary_exactly_25th_is_fair():
    # condition is strict < so exactly at 25th → fair, not cheap
    assert _pe_position_label(15.0, 15.0, 25.0, 35.0) == "fair"


def test_position_boundary_exactly_median_is_expensive():
    assert _pe_position_label(25.0, 15.0, 25.0, 35.0) == "expensive"


def test_position_boundary_exactly_75th_is_very_expensive():
    assert _pe_position_label(35.0, 15.0, 25.0, 35.0) == "very_expensive"
