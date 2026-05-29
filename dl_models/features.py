"""Feature engineering for DL models — daily, weekly, and market-level features."""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional

def compute_returns(close: np.ndarray, periods: list) -> Dict[str, np.ndarray]:
    """Compute returns over multiple periods. Returns dict keyed by 'ret_{p}d'."""
    result = {}
    for p in periods:
        ret = np.full_like(close, np.nan, dtype=np.float32)
        ret[p:] = (close[p:] / close[:-p] - 1) * 100
        result[f'ret_{p}d'] = ret
    return result

def compute_volatility(close: np.ndarray, window: int = 20) -> np.ndarray:
    """Rolling historical volatility (annualized)."""
    ret = np.full_like(close, np.nan)
    ret[1:] = (close[1:] / close[:-1] - 1)
    vol = np.full_like(close, np.nan)
    for i in range(window, len(close) + 1):
        vol[i-1] = np.nanstd(ret[i-window:i]) * np.sqrt(252)
    return vol

def compute_ma_deviation(close: np.ndarray, window: int) -> np.ndarray:
    """Price deviation from moving average, as fraction."""
    ma = np.full_like(close, np.nan)
    for i in range(window - 1, len(close)):
        ma[i] = np.mean(close[i-window+1:i+1])
    return (close - ma) / ma

def compute_rsi(close: np.ndarray, window: int = 14) -> np.ndarray:
    """RSI indicator."""
    delta = np.full_like(close, np.nan)
    delta[1:] = close[1:] - close[:-1]
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)
    avg_gain = np.full_like(close, np.nan)
    avg_loss = np.full_like(close, np.nan)
    for i in range(window, len(close)):
        avg_gain[i] = np.mean(gain[i-window+1:i+1])
        avg_loss[i] = np.mean(loss[i-window+1:i+1])
    rs = avg_gain / (avg_loss + 1e-10)
    return 100.0 - (100.0 / (1.0 + rs))

def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 14) -> np.ndarray:
    """Average True Range."""
    tr = np.full_like(close, np.nan)
    tr[1:] = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    atr = np.full_like(close, np.nan)
    for i in range(window, len(close)):
        atr[i] = np.mean(tr[i-window+1:i+1])
    return atr

def compute_volume_ratio(volume: np.ndarray, window: int = 5) -> np.ndarray:
    """Volume ratio: current volume / MA volume."""
    ma_vol = np.full_like(volume, np.nan, dtype=np.float32)
    for i in range(window - 1, len(volume)):
        ma_vol[i] = np.mean(volume[i-window+1:i+1])
    return volume / ma_vol

def build_daily_features(
    open_arr: np.ndarray, high_arr: np.ndarray, low_arr: np.ndarray,
    close_arr: np.ndarray, volume_arr: np.ndarray, amount_arr: np.ndarray,
    turnover_arr: Optional[np.ndarray] = None,
    money_flow_5d: Optional[np.ndarray] = None,
    money_flow_10d: Optional[np.ndarray] = None,
) -> Dict[str, np.ndarray]:
    """
    Build daily-frequency feature dict for a single stock.
    All input arrays are 1-D numpy float32, aligned by date (oldest->newest).
    Returns dict of feature_name -> 1-D array.
    """
    features = {}

    # Returns
    features.update(compute_returns(close_arr, [1, 3, 5, 10, 20]))

    # Volatility
    features['volatility_20d'] = compute_volatility(close_arr, 20)

    # MA deviations
    for w in [5, 10, 20, 60]:
        features[f'ma_dev_{w}d'] = compute_ma_deviation(close_arr, w)

    # RSI
    features['rsi_14'] = compute_rsi(close_arr, 14)

    # ATR ratio
    atr = compute_atr(high_arr, low_arr, close_arr, 14)
    features['atr_ratio'] = atr / close_arr

    # Volume ratio
    features['volume_ratio'] = compute_volume_ratio(volume_arr, 5)

    # Bollinger position
    ma20 = np.full_like(close_arr, np.nan)
    std20 = np.full_like(close_arr, np.nan)
    for i in range(19, len(close_arr)):
        ma20[i] = np.mean(close_arr[i-19:i+1])
        std20[i] = np.std(close_arr[i-19:i+1])
    features['bollinger_pos'] = (close_arr - ma20) / (std20 + 1e-10)

    # Amplitude
    features['amplitude'] = (high_arr - low_arr) / close_arr

    # Consecutive up/down days
    up_days = np.zeros_like(close_arr, dtype=np.float32)
    down_days = np.zeros_like(close_arr, dtype=np.float32)
    for i in range(1, len(close_arr)):
        if close_arr[i] > close_arr[i-1]:
            up_days[i] = up_days[i-1] + 1
            down_days[i] = 0
        elif close_arr[i] < close_arr[i-1]:
            down_days[i] = down_days[i-1] + 1
            up_days[i] = 0
    features['consecutive_up'] = up_days
    features['consecutive_down'] = down_days

    # Money flow (optional, from external)
    if money_flow_5d is not None:
        features['money_flow_5d'] = money_flow_5d
    if money_flow_10d is not None:
        features['money_flow_10d'] = money_flow_10d

    # Turnover
    if turnover_arr is not None:
        features['turnover_rate'] = turnover_arr

    return features

def build_market_features(
    index_close: np.ndarray,          # CSI 300 60-day close
    index_volume: np.ndarray,         # CSI 300 60-day volume
    breadth: np.ndarray,              # up_stocks / total_stocks per day
    north_flow: Optional[np.ndarray] = None,  # north-bound net flow
    sector_dispersion: Optional[np.ndarray] = None,  # sector return std
) -> np.ndarray:
    """
    Build market-level feature matrix for regime detection.
    Returns (T, N) array where T = sequence length, N = features.
    """
    features = []
    features.append((index_close - np.mean(index_close)) / np.std(index_close))
    features.append(compute_ma_deviation(index_close, 20))

    ret_5d = np.full_like(index_close, np.nan)
    ret_5d[5:] = (index_close[5:] / index_close[:-5] - 1) * 100
    features.append(ret_5d)

    vol_ratio = compute_volume_ratio(index_volume, 20)
    features.append(vol_ratio)

    features.append(breadth)

    if north_flow is not None:
        features.append(north_flow)

    if sector_dispersion is not None:
        features.append(sector_dispersion)

    return np.column_stack(features).astype(np.float32)

DAILY_FEATURE_NAMES = [
    'ret_1d', 'ret_3d', 'ret_5d', 'ret_10d', 'ret_20d',
    'volatility_20d',
    'ma_dev_5d', 'ma_dev_10d', 'ma_dev_20d', 'ma_dev_60d',
    'rsi_14', 'atr_ratio', 'volume_ratio', 'bollinger_pos', 'amplitude',
    'consecutive_up', 'consecutive_down',
    'money_flow_5d', 'money_flow_10d', 'turnover_rate',
]
