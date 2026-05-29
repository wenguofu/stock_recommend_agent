import numpy as np
import pytest
from dl_models.features import (
    compute_returns, compute_rsi, compute_atr,
    build_daily_features, build_market_features, DAILY_FEATURE_NAMES,
)

class TestComputeReturns:
    def test_ret_3d(self):
        close = np.array([10.0, 10.5, 10.2, 10.8, 11.0], dtype=np.float32)
        result = compute_returns(close, [3])
        assert 'ret_3d' in result
        assert np.isnan(result['ret_3d'][2])  # first 3 positions are NaN
        assert abs(result['ret_3d'][3] - 8.0) < 0.01  # (10.8/10.0-1)*100
        assert abs(result['ret_3d'][4] - 4.762) < 0.01  # (11.0/10.5-1)*100

class TestRSI:
    def test_rsi_range(self):
        np.random.seed(42)
        close = 100 + np.cumsum(np.random.randn(100) * 0.5)
        rsi = compute_rsi(close, 14)
        assert np.isnan(rsi[:14]).all()  # window warmup
        assert np.all((rsi[14:] >= 0) & (rsi[14:] <= 100))

class TestATR:
    def test_atr_positive(self):
        high = np.array([10.5, 11.0, 11.5, 11.2], dtype=np.float32)
        low = np.array([9.5, 10.2, 10.8, 10.5], dtype=np.float32)
        close = np.array([10.0, 10.8, 11.0, 11.0], dtype=np.float32)
        atr = compute_atr(high, low, close, 3)
        assert np.isnan(atr[:3]).all()
        assert atr[3] > 0

class TestBuildDailyFeatures:
    def test_all_features_present(self):
        n = 30
        close = 100 + np.cumsum(np.random.randn(n) * 0.5)
        open_arr = close - np.random.rand(n) * 0.3
        high = close + np.abs(np.random.randn(n)) * 0.5
        low = close - np.abs(np.random.randn(n)) * 0.5
        volume = np.random.rand(n) * 1e7 + 5e6
        amount = volume * close
        features = build_daily_features(open_arr, high, low, close, volume, amount)
        for name in DAILY_FEATURE_NAMES:
            if name not in ['money_flow_5d', 'money_flow_10d', 'turnover_rate']:
                assert name in features, f"Missing feature: {name}"
        # All arrays same length
        for v in features.values():
            assert len(v) == n
