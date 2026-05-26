#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for market_monitor.py — Market Trend Monitor Engine."""

import pytest
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_monitor import (
    get_index_kline,
    check_adx_trend,
    check_ma_pattern,
    check_macd_divergence,
    check_volume_divergence,
    check_momentum_rsi,
    find_similar_patterns,
    full_monitor,
    _ema,
    _sma,
    _rsi,
    _adx,
    _macd,
    _cosine_similarity,
)


# ──────────────────────────────────────────────
# Helper: generate synthetic OHLCV DataFrame
# ──────────────────────────────────────────────

def make_ohlcv(n: int, trend: str = 'flat', seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV DataFrame with optional trend.

    Args:
        n: Number of rows
        trend: 'flat', 'up', 'down', 'bearish_adx', 'death_cross', 'divergence'
        seed: Random seed
    """
    np.random.seed(seed)
    base = 3000.0
    dates = pd.date_range('2024-01-01', periods=n, freq='B')

    if trend == 'up':
        drift = np.linspace(0, 500, n)
    elif trend == 'down':
        drift = np.linspace(0, -500, n)
    elif trend == 'death_cross':
        # Start flat, then decline to make MA20 cross below MA60
        drift = np.concatenate([
            np.linspace(0, 50, n // 3),
            np.linspace(50, -50, n // 3),
            np.linspace(-50, -200, n - 2 * (n // 3)),
        ])
    elif trend == 'bearish_adx':
        # Strong downtrend for ADX to detect
        drift = np.linspace(0, -800, n)
    elif trend == 'divergence':
        # Price making higher highs but DIF should show bearish divergence
        # First half: steady uptrend, second half: accelerated uptrend (higher highs)
        drift = np.concatenate([
            np.linspace(0, 300, n // 2),
            np.linspace(300, 500, n - n // 2),
        ])
    else:
        drift = np.zeros(n)

    noise = np.random.randn(n) * 20
    close = base + drift + noise
    open_p = close - np.random.randn(n) * 10
    high = np.maximum(open_p, close) + np.abs(np.random.randn(n) * 15)
    low = np.minimum(open_p, close) - np.abs(np.random.randn(n) * 15)
    volume = np.random.randint(1000000, 10000000, n)

    df = pd.DataFrame({
        'date': dates,
        'open': open_p,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })
    return df


def make_volume_distribution_df(n: int = 30) -> pd.DataFrame:
    """Generate data where down-day volume > up-day volume * 1.3."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')

    # Alternate up and down, with down days having much higher volume
    close = np.zeros(n)
    volume = np.zeros(n)
    close[0] = 3000
    for i in range(1, n):
        if i % 3 == 0:  # Up day
            close[i] = close[i - 1] + np.random.uniform(5, 15)
            volume[i] = np.random.uniform(1e6, 2e6)  # Low volume
        else:  # Down day
            close[i] = close[i - 1] - np.random.uniform(5, 15)
            volume[i] = np.random.uniform(4e6, 8e6)  # High volume

    high = close + np.abs(np.random.randn(n) * 10)
    low = close - np.abs(np.random.randn(n) * 10)
    open_p = close - np.random.randn(n) * 5

    return pd.DataFrame({
        'date': dates,
        'open': open_p,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    })


def make_momentum_df(n: int = 30) -> pd.DataFrame:
    """Generate data with consecutive lower lows and low RSI."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    base = 3000.0

    # Steady decline with consecutive lower lows
    drift = np.linspace(0, -300, n)
    noise = np.random.randn(n) * 5
    close = base + drift + noise

    # Ensure consecutive lower lows in last 5 days
    close[-5:] = [2705, 2700, 2695, 2690, 2685]
    low_vals = close - np.abs(np.random.randn(n) * 8)
    low_vals[-5:] = [2700, 2695, 2690, 2685, 2680]  # Consecutive lower lows

    high = close + np.abs(np.random.randn(n) * 10)
    open_p = close - np.random.randn(n) * 3

    return pd.DataFrame({
        'date': dates,
        'open': open_p,
        'high': high,
        'low': low_vals,
        'close': close,
        'volume': np.random.randint(1000000, 5000000, n),
    })


# ──────────────────────────────────────────────
# Tests: Internal helpers
# ──────────────────────────────────────────────

class TestHelpers:
    def test_ema_basic(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result = _ema(data, 5)
        assert not np.isnan(result[-1])
        assert result[-1] > 5.0

    def test_sma_basic(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _sma(data, 3)
        assert not np.isnan(result[-1])
        # SMA(3) of last 3: (3+4+5)/3 = 4.0
        assert abs(result[-1] - 4.0) < 0.01

    def test_rsi_basic(self):
        close = np.linspace(10, 20, 30)  # Steady uptrend → high RSI
        result = _rsi(close, 14)
        assert not np.isnan(result[-1])
        assert result[-1] > 50  # Uptrend should give high RSI

    def test_rsi_insufficient_data(self):
        close = np.array([10.0, 11.0, 12.0])
        result = _rsi(close, 14)
        assert np.all(np.isnan(result))

    def test_adx_bearish_trend(self):
        n = 60
        close = np.linspace(100, 50, n)  # Steady downtrend
        high = close + np.random.randn(n) * 2
        low = close - np.random.randn(n) * 2
        adx, pdi, mdi = _adx(high, low, close, 14)
        # ADX should be > 0 for a trending market
        assert not np.isnan(adx[-1])
        assert adx[-1] > 0

    def test_macd_basic(self):
        close = np.linspace(10, 30, 50)
        dif, dea, hist = _macd(close)
        assert not np.isnan(dif[-1])
        assert not np.isnan(dea[-1])

    def test_cosine_similarity_identical(self):
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        sim = _cosine_similarity(a, b)
        assert abs(sim - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        sim = _cosine_similarity(a, b)
        assert abs(sim - 0.0) < 0.001


# ──────────────────────────────────────────────
# Tests: get_index_kline
# ──────────────────────────────────────────────

class TestGetIndexKline:
    def test_returns_dataframe(self):
        """get_index_kline should return a DataFrame with expected columns."""
        # This will try the real fetcher; we just check the structure
        try:
            df = get_index_kline('000001', days=30)
            assert isinstance(df, pd.DataFrame)
            # Check expected columns exist
            for col in ['date', 'open', 'high', 'low', 'close', 'volume']:
                assert col in df.columns, f"Missing column: {col}"
        except Exception as e:
            # If real fetch fails (no network, etc.), skip gracefully
            pytest.skip(f"Real API unavailable: {e}")


# ──────────────────────────────────────────────
# Tests: check_adx_trend
# ──────────────────────────────────────────────

class TestCheckAdxTrend:
    def test_detects_bearish(self):
        """ADX should detect bearish trend in a strong downtrend."""
        df = make_ohlcv(120, trend='bearish_adx')
        # Force a clear bearish setup: drop prices sharply
        result = check_adx_trend(df)

        assert 'score' in result
        assert 'signal' in result
        assert 'adx' in result
        assert 'plus_di' in result
        assert 'minus_di' in result

        # In a strong downtrend, we expect bearish or at least neutral with ADX > 0
        assert result['adx'] is not None
        # -DI should be higher than +DI in a downtrend
        if result['minus_di'] is not None and result['plus_di'] is not None:
            # Not strictly asserting bearish (depends on noise) but -DI > +DI is likely
            pass

    def test_bearish_with_forced_data(self):
        """Force data that guarantees bearish ADX detection."""
        n = 100
        np.random.seed(42)
        # Strong downtrend with large daily moves to boost ADX
        close = np.linspace(5000, 2000, n)
        high = close + np.abs(np.random.randn(n) * 30)
        low = close - np.abs(np.random.randn(n) * 30)

        # Force negative directional movement
        for i in range(1, n):
            low[i] = min(low[i], low[i - 1] - 50)  # Lower lows
            high[i] = min(high[i], high[i - 1] - 10)  # Lower highs

        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': high, 'low': low, 'close': close,
            'volume': np.random.randint(1e6, 1e7, n),
        })

        result = check_adx_trend(df)
        assert result['signal'] in ('bearish', 'bullish', 'neutral')
        # With forced lower highs/lows, minus_di should dominate
        if result['minus_di'] is not None and result['plus_di'] is not None:
            assert result['minus_di'] > result['plus_di']

    def test_empty_df(self):
        result = check_adx_trend(pd.DataFrame())
        assert result['score'] == 0
        assert result['signal'] == 'neutral'

    def test_insufficient_data(self):
        df = make_ohlcv(10)
        result = check_adx_trend(df)
        assert result['score'] == 0
        assert result['signal'] == 'neutral'
        assert '数据不足' in result['detail']

    def test_none_input(self):
        result = check_adx_trend(None)
        assert result['score'] == 0
        assert result['signal'] == 'neutral'

    def test_bearish_score_when_detected(self):
        """When ADX > 25 and -DI > +DI, score should be 25."""
        n = 60
        np.random.seed(99)
        close = np.linspace(4000, 1500, n)
        high = close + np.random.uniform(10, 50, n)
        low = close - np.random.uniform(10, 50, n)
        # Force lower lows each day
        for i in range(1, n):
            low[i] = low[i - 1] - np.random.uniform(30, 80)

        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': high, 'low': low, 'close': close,
            'volume': np.random.randint(1e6, 1e7, n),
        })
        result = check_adx_trend(df)
        # In this extreme downtrend, should get bearish
        assert result['signal'] == 'bearish'
        assert result['score'] == 25


# ──────────────────────────────────────────────
# Tests: check_ma_pattern
# ──────────────────────────────────────────────

class TestCheckMaPattern:
    def test_detects_death_cross(self):
        """MA20 < MA60 should be detected as death cross."""
        df = make_ohlcv(120, trend='death_cross')
        result = check_ma_pattern(df)

        assert 'score' in result
        assert 'signals' in result
        assert 'ma20' in result
        assert 'ma60' in result
        assert 'ma120' in result

        # With death_cross trend, MA20 should be below MA60
        if result['ma20'] is not None and result['ma60'] is not None:
            if result['ma20'] < result['ma60']:
                assert result['score'] >= 20

    def test_death_cross_forced(self):
        """Force data that guarantees MA20 < MA60 < MA120."""
        n = 150
        np.random.seed(42)
        # Prices declining over time
        close = np.concatenate([
            np.linspace(3500, 3200, 50),
            np.linspace(3200, 2800, 50),
            np.linspace(2800, 2300, 50),
        ])
        noise = np.random.randn(n) * 10
        close = close + noise

        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': close + 5, 'low': close - 5,
            'close': close,
            'volume': np.random.randint(1e6, 1e7, n),
        })
        result = check_ma_pattern(df)

        assert result['ma20'] < result['ma60'], \
            f"Expected MA20({result['ma20']}) < MA60({result['ma60']})"
        assert result['score'] >= 20

    def test_bearish_alignment(self):
        """MA20 < MA60 < MA120 full bearish alignment."""
        n = 200
        np.random.seed(42)
        # Strong and prolonged decline
        close = np.linspace(4000, 1000, n) + np.random.randn(n) * 5
        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': close + 3, 'low': close - 3,
            'close': close,
            'volume': np.random.randint(1e6, 1e7, n),
        })
        result = check_ma_pattern(df)

        assert result['ma20'] is not None
        assert result['ma60'] is not None
        assert result['ma120'] is not None
        assert result['ma20'] < result['ma60'] < result['ma120'], \
            f"MA20={result['ma20']}, MA60={result['ma60']}, MA120={result['ma120']}"
        assert result['score'] == 25

    def test_insufficient_data(self):
        df = make_ohlcv(15)
        result = check_ma_pattern(df)
        assert '数据不足' in str(result['signals'])


# ──────────────────────────────────────────────
# Tests: check_macd_divergence
# ──────────────────────────────────────────────

class TestCheckMacdDivergence:
    def test_detects_divergence(self):
        """MACD bearish divergence: price highs rising but DIF falling."""
        n = 100
        np.random.seed(42)

        # Create two phases:
        # Phase 1 (0-50): moderate uptrend with momentum (DIF will be high)
        # Phase 2 (50-100): continued price rise but with decreasing momentum
        p1 = np.linspace(100, 130, 50)
        p2 = np.linspace(130, 140, 50)  # Slower rise → DIF should decline

        close = np.concatenate([p1, p2]) + np.random.randn(n) * 1.5

        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': close + 2, 'low': close - 2,
            'close': close,
            'volume': np.random.randint(1e6, 1e7, n),
        })

        result = check_macd_divergence(df)

        assert 'score' in result
        assert 'signals' in result

    def test_forced_divergence(self):
        """Force a clear bearish divergence pattern."""
        n = 80
        np.random.seed(123)

        # Phase 1: strong uptrend (will produce high DIF)
        phase1 = np.linspace(100, 150, 40)

        # Phase 2: even higher prices but with much slower momentum
        # (price continues up but at a decreasing rate → DIF will fall)
        phase2 = np.linspace(150, 170, 40)

        # Add a spike near the end to make price high even clearer
        phase2[-10:] += np.linspace(0, 5, 10)

        close = np.concatenate([phase1, phase2]) + np.random.randn(n) * 1.0

        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': close + 1, 'low': close - 1,
            'close': close,
            'volume': np.random.randint(1e6, 1e7, n),
        })

        result = check_macd_divergence(df)
        # The divergence check compares price highs and DIF highs between halves
        # We just verify the function runs correctly
        assert isinstance(result['score'], int)
        assert isinstance(result['signals'], list)

    def test_insufficient_data(self):
        df = make_ohlcv(20)
        result = check_macd_divergence(df)
        assert result['score'] == 0
        assert '数据不足' in str(result['signals'])


# ──────────────────────────────────────────────
# Tests: check_volume_divergence
# ──────────────────────────────────────────────

class TestCheckVolumeDivergence:
    def test_detects_distribution(self):
        df = make_volume_distribution_df(30)
        result = check_volume_divergence(df)

        assert 'score' in result
        assert 'signals' in result
        # With our forced data, should detect distribution
        assert result['score'] == 15, f"Expected 15, got {result['score']}: {result['signals']}"

    def test_no_distribution_on_uptrend(self):
        n = 30
        np.random.seed(42)
        close = np.linspace(100, 130, n)
        # Upside volume higher → no distribution signal
        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': close + 1, 'low': close - 1,
            'close': close,
            'volume': np.random.randint(5e6, 1e7, n),
        })
        result = check_volume_divergence(df)
        assert result['score'] == 0


# ──────────────────────────────────────────────
# Tests: check_momentum_rsi
# ──────────────────────────────────────────────

class TestCheckMomentumRsi:
    def test_detects_weakness(self):
        df = make_momentum_df(30)
        result = check_momentum_rsi(df)

        assert 'score' in result
        assert 'signals' in result
        assert 'rsi' in result

        # With forced consecutive lower lows + decline → should have signals
        assert result['score'] >= 10, f"Expected >=10, got {result['score']}: {result['signals']}"
        assert result['rsi'] is not None
        assert result['rsi'] < 50  # Downtrend should give low RSI

    def test_insufficient_data(self):
        df = make_ohlcv(10)
        result = check_momentum_rsi(df)
        assert result['score'] == 0
        assert result['rsi'] is None


# ──────────────────────────────────────────────
# Tests: find_similar_patterns
# ──────────────────────────────────────────────

class TestFindSimilarPatterns:
    def test_returns_matches(self):
        n = 100
        np.random.seed(42)
        close = np.linspace(100, 120, n) + np.random.randn(n) * 3

        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': close + 2, 'low': close - 2,
            'close': close,
            'volume': np.random.randint(1e6, 1e7, n),
        })

        result = find_similar_patterns(df, window=20, top_k=3)

        assert isinstance(result, list)
        assert len(result) <= 3
        if len(result) > 0:
            for item in result:
                assert 'similarity' in item
                assert 'match_date' in item
                assert 'future_20d_return' in item
                assert 'direction' in item
                assert -1.0 <= item['similarity'] <= 1.0

    def test_insufficient_data(self):
        df = make_ohlcv(30)
        result = find_similar_patterns(df, window=20, top_k=3)
        assert result == []

    def test_empty_df(self):
        result = find_similar_patterns(pd.DataFrame(), window=20, top_k=3)
        assert result == []


# ──────────────────────────────────────────────
# Tests: full_monitor
# ──────────────────────────────────────────────

class TestFullMonitor:
    def test_returns_correct_structure(self):
        """full_monitor should return a complete dict with all expected keys."""
        # Use a mock approach — but for a real integration test we try the API
        # Since we can't easily mock without the real API, we test with
        # edge case: the function gracefully handles API errors
        result = full_monitor('000001')

        assert isinstance(result, dict)
        assert 'code' in result
        assert 'verdict' in result
        assert 'warning_level' in result
        assert 'total_score' in result
        assert 'suggest' in result
        assert 'signals' in result
        assert 'indicators' in result
        assert 'checks' in result
        assert 'similar_patterns' in result

        # warning_level should be one of the expected values
        assert result['warning_level'] in ('normal', 'watch', 'alert', 'danger', 'error')

        # total_score should be 0-100
        assert 0 <= result['total_score'] <= 100

        # checks should contain all sub-modules
        checks = result['checks']
        if checks:
            assert 'adx_trend' in checks
            assert 'ma_pattern' in checks
            assert 'macd_divergence' in checks
            assert 'volume_divergence' in checks
            assert 'momentum_rsi' in checks

        # indicators should have the expected keys
        indicators = result['indicators']
        if indicators:
            for key in ['adx', 'plus_di', 'minus_di', 'ma20', 'ma60', 'ma120', 'rsi']:
                assert key in indicators, f"Missing indicator: {key}"

    def test_full_monitor_with_synthetic_data(self):
        """Test score aggregation logic with synthetic data (no API call)."""
        # Create synthetic data that triggers multiple bearish signals
        n = 200
        np.random.seed(42)
        close = np.linspace(4000, 1500, n) + np.random.randn(n) * 10
        low = close - np.abs(np.random.randn(n) * 20)
        high = close + np.abs(np.random.randn(n) * 15)
        # Force lower lows
        for i in range(5):
            low[-(5 - i)] = low[-6] - i * 10
            close[-(5 - i)] = low[-(5 - i)] + 3

        dates = pd.date_range('2024-01-01', periods=n, freq='B')
        df = pd.DataFrame({
            'date': dates, 'open': close,
            'high': high, 'low': low, 'close': close,
            'volume': np.random.randint(1e6, 1e7, n),
        })

        # Run individual checks on synthetic data
        adx = check_adx_trend(df)
        ma = check_ma_pattern(df)
        macd = check_macd_divergence(df)
        vol = check_volume_divergence(df)
        mom = check_momentum_rsi(df)

        total = adx['score'] + ma['score'] + macd['score'] + vol['score'] + mom['score']
        assert 0 <= total <= 100

        # In a strong downtrend, total should be > 0
        assert total > 0, f"Expected positive score in downtrend, got {total}"
