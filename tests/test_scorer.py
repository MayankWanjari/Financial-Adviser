"""Tests for scorer.py"""

import pytest
from data.scorer import (
    _score_value,
    _score_quality,
    _score_safety,
    _score_graham_gap,
    _score_profitability,
    _score_dividend,
    _grade,
    _generate_interpretation,
    load_scoring_config
)

cfg = load_scoring_config()

# ─── Value (PE) ───

def test_score_value_excellent():
    score, detail = _score_value(12.0, cfg["value"])
    assert score == 20

def test_score_value_fair():
    score, detail = _score_value(18.0, cfg["value"])
    assert score == 15

def test_score_value_expensive():
    score, detail = _score_value(55.0, cfg["value"])
    assert score == 0

def test_score_value_none():
    score, detail = _score_value(None, cfg["value"])
    assert score == 0

# ─── Quality (ROE) ───

def test_score_quality_excellent():
    score, detail = _score_quality(0.26, cfg["quality"]) # 26%
    assert score == 20

def test_score_quality_poor():
    score, detail = _score_quality(0.04, cfg["quality"]) # 4%
    assert score == 0

def test_score_quality_none():
    score, detail = _score_quality(None, cfg["quality"])
    assert score == 0

# ─── Safety (D/E) ───

def test_score_safety_very_low():
    score, detail = _score_safety(0.2, cfg["safety"])
    assert score == 15

def test_score_safety_high():
    score, detail = _score_safety(3.0, cfg["safety"])
    assert score == 0

def test_score_safety_none():
    score, detail = _score_safety(None, cfg["safety"])
    assert score == 0

# ─── Graham Gap ───

def test_score_graham_gap_deep_value():
    # GN = sqrt(22.5 * 100 * 50) = ~335
    # Price = 200. Margin = (335-200)/335 = ~40%
    score, detail = _score_graham_gap(eps=100.0, book_value=50.0, price=200.0, cfg=cfg["graham_gap"])
    assert score == 20

def test_score_graham_gap_premium():
    # Price = 400. Margin = (335-400)/335 = ~-19%
    score, detail = _score_graham_gap(eps=100.0, book_value=50.0, price=400.0, cfg=cfg["graham_gap"])
    assert score == 5

def test_score_graham_gap_missing_data():
    score, detail = _score_graham_gap(eps=None, book_value=50.0, price=200.0, cfg=cfg["graham_gap"])
    assert score == 0

# ─── Profitability (Net Margin) ───

def test_score_profitability_high():
    score, detail = _score_profitability(0.22, cfg["profitability"]) # 22%
    assert score == 15

def test_score_profitability_low():
    score, detail = _score_profitability(0.02, cfg["profitability"]) # 2%
    assert score == 0

def test_score_profitability_none():
    score, detail = _score_profitability(None, cfg["profitability"])
    assert score == 0

# ─── Dividend ───

def test_score_dividend_high():
    score, detail = _score_dividend(4.5, cfg["dividend"]) # 4.5%
    assert score == 10

def test_score_dividend_low():
    score, detail = _score_dividend(0.5, cfg["dividend"]) # 0.5%
    assert score == 2

def test_score_dividend_none():
    score, detail = _score_dividend(None, cfg["dividend"])
    assert score == 0
    
def test_score_dividend_zero():
    score, detail = _score_dividend(0, cfg["dividend"])
    assert score == 0

# ─── Grade ───

def test_grade_boundaries():
    gc = cfg["grades"]
    assert _grade(100, gc) == "A"
    assert _grade(80, gc) == "A"
    assert _grade(79, gc) == "B"
    assert _grade(65, gc) == "B"
    assert _grade(64, gc) == "C"
    assert _grade(50, gc) == "C"
    assert _grade(49, gc) == "D"
    assert _grade(35, gc) == "D"
    assert _grade(34, gc) == "F"
    assert _grade(0, gc) == "F"

# ─── Interpretation ───

def test_generate_interpretation():
    breakdown = {
        "value":         {"score": 20, "max": 20, "detail": ""},
        "quality":       {"score": 20, "max": 20, "detail": ""},
        "safety":        {"score": 15, "max": 15, "detail": ""},
        "graham_gap":    {"score": 20, "max": 20, "detail": ""},
        "profitability": {"score": 15, "max": 15, "detail": ""},
        "dividend":      {"score": 10, "max": 10, "detail": ""},
    }
    interp = _generate_interpretation(breakdown, {})
    assert "Strong fundamentals" in interp
