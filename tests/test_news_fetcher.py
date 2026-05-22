"""Tests for data/news_fetcher.py pure helpers — no network calls."""

from datetime import datetime, timezone, timedelta
from pathlib import Path

from data.news_fetcher import (
    DEDUP_SIMILARITY_THRESHOLD,
    _headline_similarity,
    _is_within_24h,
    _matches_symbol_or_name,
    build_symbol_name_map,
)


# ── _headline_similarity ──────────────────────────────────────────────────────

def test_identical_headlines_score_1():
    score = _headline_similarity("Reliance Q4 profit rises 10%", "Reliance Q4 profit rises 10%")
    assert score == 1.0


def test_completely_different_headlines_score_low():
    score = _headline_similarity("Reliance buys stake in Jio", "RBI keeps repo rate unchanged")
    assert score < DEDUP_SIMILARITY_THRESHOLD


def test_similar_headlines_score_above_threshold():
    a = "Reliance Industries Q4 profit rises 10 percent"
    b = "Reliance Industries Q4 profits rise 10 percent"
    assert _headline_similarity(a, b) >= DEDUP_SIMILARITY_THRESHOLD


def test_similarity_is_case_insensitive():
    assert _headline_similarity("TCS WINS CONTRACT", "tcs wins contract") == 1.0


def test_similarity_returns_float_between_0_and_1():
    score = _headline_similarity("some headline", "other headline")
    assert 0.0 <= score <= 1.0


# ── _is_within_24h ────────────────────────────────────────────────────────────

def test_article_published_now_is_within_24h():
    article = {"published": datetime.now(timezone.utc)}
    assert _is_within_24h(article) is True


def test_article_published_1h_ago_is_within_24h():
    article = {"published": datetime.now(timezone.utc) - timedelta(hours=1)}
    assert _is_within_24h(article) is True


def test_article_published_25h_ago_is_stale():
    article = {"published": datetime.now(timezone.utc) - timedelta(hours=25)}
    assert _is_within_24h(article) is False


def test_article_published_just_over_24h_is_stale():
    article = {"published": datetime.now(timezone.utc) - timedelta(hours=24, seconds=1)}
    assert _is_within_24h(article) is False


# ── _matches_symbol_or_name ───────────────────────────────────────────────────

def test_matches_exact_ticker():
    assert _matches_symbol_or_name("TCS wins big contract", "TCS", []) is True


def test_matches_alt_name():
    assert _matches_symbol_or_name(
        "Tata Consultancy Services wins deal", "TCS", ["Tata Consultancy Services"]
    ) is True


def test_no_match_on_unrelated_text():
    assert _matches_symbol_or_name("RBI holds interest rates", "TCS", ["Tata Consultancy"]) is False


def test_no_false_positive_substring():
    # "TCS" should NOT match inside "tactics"
    assert _matches_symbol_or_name("new tactics used by firm", "TCS", []) is False


def test_case_insensitive_matching():
    assert _matches_symbol_or_name("reliance gains 5%", "RELIANCE", []) is True


def test_matches_ticker_with_ampersand():
    # L&T has a special character — re.escape must handle it
    assert _matches_symbol_or_name("L&T wins infra order", "LT", ["L&T"]) is True


def test_empty_text_returns_false():
    assert _matches_symbol_or_name("", "TCS", ["Tata Consultancy"]) is False


# ── build_symbol_name_map ─────────────────────────────────────────────────────

def test_build_symbol_name_map_with_alt_names(tmp_path):
    watchlist = tmp_path / "watchlist.txt"
    watchlist.write_text(
        "TCS  # Tata Consultancy, TCS Ltd\nINFY\n# Comment line\n",
        encoding="utf-8",
    )
    result = build_symbol_name_map(watchlist)
    assert result["TCS"] == ["Tata Consultancy", "TCS Ltd"]
    assert result["INFY"] == []


def test_build_symbol_name_map_skips_comment_lines(tmp_path):
    watchlist = tmp_path / "watchlist.txt"
    watchlist.write_text("# This is a comment\nRELIANCE\n", encoding="utf-8")
    result = build_symbol_name_map(watchlist)
    assert "RELIANCE" in result
    assert len(result) == 1


def test_build_symbol_name_map_missing_file_returns_empty(tmp_path):
    result = build_symbol_name_map(tmp_path / "nonexistent.txt")
    assert result == {}


def test_build_symbol_name_map_normalises_tickers_to_upper(tmp_path):
    watchlist = tmp_path / "watchlist.txt"
    watchlist.write_text("reliance\ntcs\n", encoding="utf-8")
    result = build_symbol_name_map(watchlist)
    assert "RELIANCE" in result
    assert "TCS" in result
