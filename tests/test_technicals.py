"""Tests for data/technicals.py pure helpers — no network calls."""

from data.technicals import _calculate_rsi, _get_trend_signal


# ── _calculate_rsi ────────────────────────────────────────────────────────────

def test_rsi_returns_none_when_too_few_points():
    assert _calculate_rsi([100.0] * 10) is None  # needs period+1 = 15 points


def test_rsi_all_gains_returns_100():
    closes = list(range(1, 17))  # 1, 2, …, 16 — monotonically increasing, all gains
    assert _calculate_rsi(closes) == 100.0


def test_rsi_all_losses_returns_0():
    closes = list(range(16, 0, -1))  # 16, 15, …, 1 — monotonically decreasing, all losses
    assert _calculate_rsi(closes) == 0.0


def test_rsi_neutral_range():
    # Alternating equal gains and losses keeps RSI near 50
    closes = [100 + (5 if i % 2 == 0 else -5) for i in range(20)]
    rsi = _calculate_rsi(closes)
    assert rsi is not None
    assert 30 <= rsi <= 70


def test_rsi_custom_period():
    closes = list(range(1, 22))  # 21 points → enough for period=20
    rsi = _calculate_rsi(closes, period=20)
    assert rsi is not None


def test_rsi_returns_float_not_none_for_sufficient_data():
    closes = [100.0 + i * 0.5 for i in range(20)]
    rsi = _calculate_rsi(closes)
    assert isinstance(rsi, float)


def test_rsi_result_between_0_and_100():
    closes = [100, 102, 101, 103, 102, 104, 103, 105, 104, 106,
              105, 107, 106, 108, 107, 109, 108, 110, 109, 111]
    rsi = _calculate_rsi(closes)
    assert rsi is not None
    assert 0.0 <= rsi <= 100.0


# ── _get_trend_signal ─────────────────────────────────────────────────────────

def test_trend_bullish_strong_uptrend():
    # price > sma50 > sma200
    assert _get_trend_signal(120, 110, 100) == "Bullish (strong uptrend)"


def test_trend_neutral_pullback():
    # sma50 > price > sma200 — pulling back inside an uptrend
    assert _get_trend_signal(105, 110, 100) == "Neutral (pulling back in uptrend)"


def test_trend_bearish_strong_downtrend():
    # price < sma50 < sma200
    assert _get_trend_signal(80, 90, 100) == "Bearish (strong downtrend)"


def test_trend_mixed():
    # price > sma50 but sma50 < sma200 — doesn't fit any clean pattern
    assert _get_trend_signal(105, 100, 110) == "Mixed"


def test_trend_only_sma50_bullish():
    assert _get_trend_signal(110, 100, None) == "Bullish"


def test_trend_only_sma50_bearish():
    assert _get_trend_signal(90, 100, None) == "Bearish"


def test_trend_no_smas_returns_na():
    assert _get_trend_signal(100, None, None) == "N/A"
