#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Market Trend Monitor Engine — 市场趋势监控核心模块

Pure Python + NumPy implementation of technical indicators (ADX, RSI, MACD, MA)
for A-share index trend assessment.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from data_fetchers import get_daily_kline


# ──────────────────────────────────────────────
# Internal indicator computation helpers
# ──────────────────────────────────────────────

def _ema(series: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average (EMA) using Wilder's smoothing."""
    result = np.full_like(series, np.nan, dtype=np.float64)
    if len(series) < period:
        return result
    # Seed with SMA for the first period
    result[period - 1] = np.mean(series[:period])
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(series)):
        result[i] = (series[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _sma(series: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    result = np.full_like(series, np.nan, dtype=np.float64)
    if len(series) < period:
        return result
    cumsum = np.cumsum(np.insert(series, 0, 0))
    result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder's RSI."""
    n = len(close)
    result = np.full(n, np.nan, dtype=np.float64)
    if n < period + 1:
        return result

    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    # First average
    avg_gain = np.mean(gain[:period])
    avg_loss = np.mean(loss[:period])
    if avg_loss == 0:
        result[period] = 100.0
    else:
        result[period] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    # Wilder smoothing for the rest
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            result[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    return result


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute ADX, +DI, -DI manually. Returns (adx, plus_di, minus_di)."""
    n = len(close)
    adx = np.full(n, np.nan, dtype=np.float64)
    plus_di = np.full(n, np.nan, dtype=np.float64)
    minus_di = np.full(n, np.nan, dtype=np.float64)

    if n < period * 2:
        return adx, plus_di, minus_di

    # True Range
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1]),
        ),
    )

    # Directional Movement
    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    # Smoothed values with Wilder's method
    atr = np.full(n - 1, np.nan, dtype=np.float64)
    atr_smooth = np.full(n - 1, np.nan, dtype=np.float64)
    pdm_smooth = np.full(n - 1, np.nan, dtype=np.float64)
    mdm_smooth = np.full(n - 1, np.nan, dtype=np.float64)

    # Initial values
    atr[period - 1] = np.mean(tr[:period])
    pdm_smooth[period - 1] = np.mean(plus_dm[:period])
    mdm_smooth[period - 1] = np.mean(minus_dm[:period])

    for i in range(period, n - 1):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
        pdm_smooth[i] = (pdm_smooth[i - 1] * (period - 1) + plus_dm[i]) / period
        mdm_smooth[i] = (mdm_smooth[i - 1] * (period - 1) + minus_dm[i]) / period

    # +DI / -DI / DX / ADX
    for i in range(period, n - 1):
        if atr[i] == 0:
            continue
        pdi = 100.0 * pdm_smooth[i] / atr[i]
        mdi = 100.0 * mdm_smooth[i] / atr[i]
        plus_di[i + 1] = pdi
        minus_di[i + 1] = mdi

        denom = pdi + mdi
        if denom == 0:
            continue
        dx = 100.0 * abs(pdi - mdi) / denom
        # ADX is smoothed DX
        if i == period:
            adx_sum = dx
            for j in range(period - 1, i):
                if atr[j] != 0:
                    pdi_j = 100.0 * pdm_smooth[j] / atr[j]
                    mdi_j = 100.0 * mdm_smooth[j] / atr[j]
                    d = pdi_j + mdi_j
                    if d != 0:
                        adx_sum += 100.0 * abs(pdi_j - mdi_j) / d
            adx[i + 1] = adx_sum / period
        else:
            prev_adx = adx[i]
            if not np.isnan(prev_adx):
                adx[i + 1] = (prev_adx * (period - 1) + dx) / period

    return adx, plus_di, minus_di


def _macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute MACD. Returns (DIF, DEA, MACD_histogram)."""
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal)
    # dea uses EMA smoothing on dif values, but we need to handle nans
    # _ema already handles seed with SMA, but dif has nans before slow period
    # Let's compute dea only from valid dif values
    dea_filled = np.full_like(dif, np.nan, dtype=np.float64)
    valid_mask = ~np.isnan(dif)
    if valid_mask.sum() >= signal:
        valid_idx = np.where(valid_mask)[0]
        valid_dif = dif[valid_idx]
        valid_dea = _ema(valid_dif, signal)
        dea_filled[valid_idx] = valid_dea

    macd_hist = 2.0 * (dif - dea_filled)
    return dif, dea_filled, macd_hist


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


# ──────────────────────────────────────────────
# Public API functions
# ──────────────────────────────────────────────

def get_index_kline(code: str = '000001', days: int = 180) -> pd.DataFrame:
    """Fetch index daily K-line data from data_fetchers.

    Args:
        code: Stock/index code (default '000001' for 上证指数)
        days: Number of trading days to fetch

    Returns:
        DataFrame with columns [date, open, high, low, close, volume]
    """
    return get_daily_kline(code, count=days)


def check_adx_trend(df: pd.DataFrame) -> Dict:
    """ADX trend direction analysis.

    Bearish when ADX > 25 and -DI > +DI → score 25.
    Bullish when ADX > 25 and +DI > -DI → score 0 (normal).
    Neutral otherwise → score 0.

    Returns:
        Dict with score, signal, detail, adx, plus_di, minus_di
    """
    required_cols = ['high', 'low', 'close']
    if df is None or df.empty or not all(c in df.columns for c in required_cols):
        return {
            'score': 0, 'signal': 'neutral', 'detail': '数据不足',
            'adx': None, 'plus_di': None, 'minus_di': None
        }

    if len(df) < 28:  # Need at least 2*14 for ADX
        return {
            'score': 0, 'signal': 'neutral', 'detail': f'数据不足(需≥28行,当前{len(df)}行)',
            'adx': None, 'plus_di': None, 'minus_di': None
        }

    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)

    adx_arr, plus_di_arr, minus_di_arr = _adx(high, low, close, period=14)

    # Get latest valid values
    latest_adx = float(adx_arr[-1]) if not np.isnan(adx_arr[-1]) else None
    latest_plus_di = float(plus_di_arr[-1]) if not np.isnan(plus_di_arr[-1]) else None
    latest_minus_di = float(minus_di_arr[-1]) if not np.isnan(minus_di_arr[-1]) else None

    if latest_adx is None or latest_plus_di is None or latest_minus_di is None:
        return {
            'score': 0, 'signal': 'neutral', 'detail': 'ADX计算异常',
            'adx': latest_adx, 'plus_di': latest_plus_di, 'minus_di': latest_minus_di
        }

    if latest_adx > 25:
        if latest_minus_di > latest_plus_di:
            return {
                'score': 25, 'signal': 'bearish',
                'detail': f'ADX={latest_adx:.1f}>25 且 -DI({latest_minus_di:.1f}) > +DI({latest_plus_di:.1f}),空头趋势确认',
                'adx': round(latest_adx, 2),
                'plus_di': round(latest_plus_di, 2),
                'minus_di': round(latest_minus_di, 2)
            }
        else:
            return {
                'score': 0, 'signal': 'bullish',
                'detail': f'ADX={latest_adx:.1f}>25 且 +DI({latest_plus_di:.1f}) > -DI({latest_minus_di:.1f}),多头趋势',
                'adx': round(latest_adx, 2),
                'plus_di': round(latest_plus_di, 2),
                'minus_di': round(latest_minus_di, 2)
            }
    else:
        return {
            'score': 0, 'signal': 'neutral',
            'detail': f'ADX={latest_adx:.1f}≤25,无明显趋势',
            'adx': round(latest_adx, 2),
            'plus_di': round(latest_plus_di, 2),
            'minus_di': round(latest_minus_di, 2)
        }


def check_ma_pattern(df: pd.DataFrame) -> Dict:
    """Moving Average pattern analysis.

    - MA20 < MA60 → 20 points (death cross candidate)
    - Price < MA120 → 15 points (below long-term average)
    - MA20 < MA60 < MA120 → 25 points (full bearish alignment)

    Returns:
        Dict with score, signals, ma20, ma60, ma120
    """
    required_cols = ['close']
    if df is None or df.empty or 'close' not in df.columns:
        return {
            'score': 0, 'signals': [], 'ma20': None, 'ma60': None, 'ma120': None
        }

    close = df['close'].values.astype(np.float64)
    n = len(close)
    score = 0
    signals = []

    if n < 20:
        return {'score': 0, 'signals': ['数据不足(需≥20行)'], 'ma20': None, 'ma60': None, 'ma120': None}

    ma20_arr = _sma(close, 20)
    ma20 = round(float(ma20_arr[-1]), 2) if not np.isnan(ma20_arr[-1]) else None

    ma60_arr = _sma(close, 60) if n >= 60 else np.full(n, np.nan)
    ma60 = round(float(ma60_arr[-1]), 2) if not np.isnan(ma60_arr[-1]) else None

    ma120_arr = _sma(close, 120) if n >= 120 else np.full(n, np.nan)
    ma120 = round(float(ma120_arr[-1]), 2) if not np.isnan(ma120_arr[-1]) else None

    latest_close = float(close[-1])

    # Check MA20 vs MA60 death cross
    if ma20 is not None and ma60 is not None:
        if ma20 < ma60:
            score += 20
            signals.append(f'MA20({ma20}) < MA60({ma60}),死叉信号')
        # Full bearish alignment
        if ma120 is not None and ma20 < ma60 < ma120:
            score += 5  # additional 5 on top of the 20, making total 25
            signals.append(f'MA20({ma20}) < MA60({ma60}) < MA120({ma120}),空头排列')

    # Price vs MA120
    if ma120 is not None:
        if latest_close < ma120:
            score += 15
            signals.append(f'收盘价({latest_close}) < MA120({ma120}),跌破年线')

    if not signals:
        signals.append('均线形态正常')

    return {
        'score': min(score, 25),  # Cap at 25 as specified
        'signals': signals,
        'ma20': ma20,
        'ma60': ma60,
        'ma120': ma120,
    }


def check_macd_divergence(df: pd.DataFrame) -> Dict:
    """MACD bearish divergence detection.

    Bearish divergence: price making higher highs but DIF making lower highs
    in the recent ~40 periods.

    Returns:
        Dict with score(15) and signals list
    """
    required_cols = ['close']
    if df is None or df.empty or 'close' not in df.columns:
        return {'score': 0, 'signals': ['数据不足']}

    close = df['close'].values.astype(np.float64)
    if len(close) < 40:
        return {'score': 0, 'signals': [f'数据不足(需≥40行,当前{len(close)}行)']}

    dif, dea, hist = _macd(close)

    # Get last ~40 valid DIF values
    lookback = 40
    dif_recent = dif[-lookback:]
    close_recent = close[-lookback:]

    valid_mask = ~np.isnan(dif_recent)
    if valid_mask.sum() < 20:
        return {'score': 0, 'signals': ['MACD数据不足']}

    # Find price highs in two halves
    mid = lookback // 2
    first_half_close = close_recent[:mid]
    second_half_close = close_recent[mid:]
    first_half_dif = dif_recent[:mid]
    second_half_dif = dif_recent[mid:]

    price_high_1 = np.max(first_half_close)
    price_high_2 = np.max(second_half_close)
    dif_high_1 = np.nanmax(first_half_dif)
    dif_high_2 = np.nanmax(second_half_dif)

    if price_high_2 > price_high_1 * 1.01 and dif_high_2 < dif_high_1:
        return {
            'score': 15,
            'signals': [
                f'顶背离: 价格创新高({price_high_2:.2f} > {price_high_1:.2f})但DIF走低({dif_high_2:.4f} < {dif_high_1:.4f})'
            ]
        }
    else:
        return {'score': 0, 'signals': ['无顶背离']}


def check_volume_divergence(df: pd.DataFrame) -> Dict:
    """Volume distribution signal.

    Distribution signal when average volume on down days > average volume on up days * 1.3.

    Returns:
        Dict with score(15) and signals list
    """
    required_cols = ['close', 'volume']
    if df is None or df.empty or not all(c in df.columns for c in required_cols):
        return {'score': 0, 'signals': ['数据不足']}

    close = df['close'].values.astype(np.float64)
    volume = df['volume'].values.astype(np.float64)

    if len(close) < 20:
        return {'score': 0, 'signals': [f'数据不足(需≥20行,当前{len(close)}行)']}

    # Look at last 20 days
    recent_close = close[-20:]
    recent_volume = volume[-20:]

    up_days = recent_close[1:] > recent_close[:-1]
    down_days = recent_close[1:] < recent_close[:-1]

    up_volumes = recent_volume[1:][up_days]
    down_volumes = recent_volume[1:][down_days]

    if len(up_volumes) == 0 or len(down_volumes) == 0:
        return {'score': 0, 'signals': ['无有效涨跌日']}

    avg_up_vol = np.mean(up_volumes)
    avg_down_vol = np.mean(down_volumes)

    if avg_down_vol > avg_up_vol * 1.3:
        ratio = avg_down_vol / avg_up_vol
        return {
            'score': 15,
            'signals': [
                f'放量下跌: 下跌日均量({avg_down_vol:.0f}) > 上涨日均量({avg_up_vol:.0f}) ×1.3,比值={ratio:.2f}'
            ]
        }
    else:
        ratio = avg_down_vol / avg_up_vol if avg_up_vol > 0 else float('inf')
        return {
            'score': 0,
            'signals': [f'量价正常,下跌/上涨量比={ratio:.2f}']
        }


def check_momentum_rsi(df: pd.DataFrame) -> Dict:
    """Momentum and RSI weakness detection.

    - Consecutive lower lows (3+ consecutive days) → 10 points
    - RSI < 40 → 10 points

    Returns:
        Dict with score, signals, rsi
    """
    required_cols = ['low', 'close']
    if df is None or df.empty or not all(c in df.columns for c in required_cols):
        return {'score': 0, 'signals': [], 'rsi': None}

    low = df['low'].values.astype(np.float64)
    close = df['close'].values.astype(np.float64)

    if len(close) < 14:
        return {'score': 0, 'signals': [f'数据不足(需≥14行,当前{len(close)}行)'], 'rsi': None}

    score = 0
    signals = []

    # Check consecutive lower lows (last 10 days)
    lookback = min(10, len(low))
    recent_low = low[-lookback:]
    consec_lower = 0
    max_consec = 0
    for i in range(1, len(recent_low)):
        if recent_low[i] < recent_low[i - 1]:
            consec_lower += 1
            max_consec = max(max_consec, consec_lower)
        else:
            consec_lower = 0

    if max_consec >= 3:
        score += 10
        signals.append(f'连续{max_consec}日低点下移,动能衰竭')

    # RSI
    rsi_arr = _rsi(close, 14)
    latest_rsi = round(float(rsi_arr[-1]), 1) if not np.isnan(rsi_arr[-1]) else None

    if latest_rsi is not None and latest_rsi < 40:
        score += 10
        signals.append(f'RSI({latest_rsi}) < 40,弱势区域')

    if not signals:
        signals.append('动能正常')

    return {'score': score, 'signals': signals, 'rsi': latest_rsi}


def find_similar_patterns(df: pd.DataFrame, window: int = 20, top_k: int = 3) -> List[Dict]:
    """Find historical windows similar to the most recent price pattern.

    Uses cosine similarity on 20-day return vectors.

    Args:
        df: DataFrame with 'close' column
        window: Sliding window size (default 20)
        top_k: Number of top matches to return

    Returns:
        List of dicts with similarity, match_date, future_20d_return, direction
    """
    required_cols = ['close']
    if df is None or df.empty or 'close' not in df.columns:
        return []

    close = df['close'].values.astype(np.float64)

    min_required = window * 2 + top_k
    if len(close) < min_required:
        return []

    # Calculate daily returns
    returns = np.diff(close) / close[:-1]

    # Recent window (most recent `window` returns)
    recent_vec = returns[-(window):].astype(np.float64)
    recent_vec = recent_vec / (np.linalg.norm(recent_vec) + 1e-12)

    # Slide through historical windows
    similarities = []
    max_idx = len(returns) - window - window  # Leave room for future return

    for i in range(max_idx):
        hist_vec = returns[i:i + window].astype(np.float64)
        hist_vec = hist_vec / (np.linalg.norm(hist_vec) + 1e-12)
        sim = _cosine_similarity(recent_vec, hist_vec)

        # Future return (next window days)
        future_start = i + window
        future_end = min(future_start + window, len(close))
        if future_end > future_start:
            future_return = (close[future_end - 1] - close[future_start - 1]) / close[future_start - 1]
            direction = 'up' if future_return > 0 else 'down'
        else:
            future_return = 0.0
            direction = 'flat'

        match_date = None
        if 'date' in df.columns:
            match_date = str(df['date'].iloc[i + window - 1])[:10]

        similarities.append({
            'similarity': round(float(sim), 4),
            'match_date': match_date,
            'future_20d_return': round(float(future_return), 4),
            'direction': direction,
        })

    # Sort by similarity descending
    similarities.sort(key=lambda x: x['similarity'], reverse=True)

    return similarities[:top_k]


def full_monitor(code: str = '000001') -> Dict:
    """Full market monitor — aggregates all checks.

    Computes total score (0-100) and maps to warning level:
    - normal: 0-20
    - watch: 21-40
    - alert: 41-60
    - danger: 61-100

    Args:
        code: Index/stock code to monitor

    Returns:
        Complete dict with verdict, suggest, signals, indicators
    """
    try:
        df = get_index_kline(code, days=200)  # Fetch enough for all indicators
    except Exception as e:
        return {
            'code': code,
            'verdict': 'error',
            'warning_level': 'error',
            'total_score': 0,
            'suggest': f'数据获取失败: {str(e)}',
            'signals': [],
            'indicators': {},
            'checks': {},
            'similar_patterns': [],
        }

    if df is None or df.empty:
        return {
            'code': code,
            'verdict': '数据不足',
            'warning_level': 'normal',
            'total_score': 0,
            'suggest': '无可用数据',
            'signals': [],
            'indicators': {},
            'checks': {},
            'similar_patterns': [],
        }

    # Run all checks
    adx_result = check_adx_trend(df)
    ma_result = check_ma_pattern(df)
    macd_result = check_macd_divergence(df)
    volume_result = check_volume_divergence(df)
    momentum_result = check_momentum_rsi(df)
    similar_patterns = find_similar_patterns(df, window=20, top_k=3)

    checks = {
        'adx_trend': adx_result,
        'ma_pattern': ma_result,
        'macd_divergence': macd_result,
        'volume_divergence': volume_result,
        'momentum_rsi': momentum_result,
    }

    total_score = (
        adx_result['score']
        + ma_result['score']
        + macd_result['score']
        + volume_result['score']
        + momentum_result['score']
    )
    total_score = min(total_score, 100)

    # Warning level
    if total_score <= 20:
        warning_level = 'normal'
    elif total_score <= 40:
        warning_level = 'watch'
    elif total_score <= 60:
        warning_level = 'alert'
    else:
        warning_level = 'danger'

    # Verdict
    verdict_map = {
        'normal': '市场正常',
        'watch': '注意风险',
        'alert': '高度警惕',
        'danger': '危险信号',
    }
    verdict = verdict_map[warning_level]

    # Suggestions
    suggest_map = {
        'normal': '趋势健康,可正常操作',
        'watch': '部分指标转弱,建议减仓或观望',
        'alert': '多项指标预警,建议大幅减仓',
        'danger': '多个危险信号叠加,建议清仓或做空对冲',
    }
    suggest = suggest_map[warning_level]

    # Collect all signals
    all_signals = []
    for check_name, check_result in checks.items():
        if 'signals' in check_result:
            for s in check_result['signals']:
                if s and '正常' not in s and '无' not in s:
                    all_signals.append(f'[{check_name}] {s}')

    # Indicators summary
    indicators = {
        'adx': adx_result.get('adx'),
        'plus_di': adx_result.get('plus_di'),
        'minus_di': adx_result.get('minus_di'),
        'ma20': ma_result.get('ma20'),
        'ma60': ma_result.get('ma60'),
        'ma120': ma_result.get('ma120'),
        'rsi': momentum_result.get('rsi'),
    }

    return {
        'code': code,
        'verdict': verdict,
        'warning_level': warning_level,
        'total_score': total_score,
        'suggest': suggest,
        'signals': all_signals,
        'indicators': indicators,
        'checks': checks,
        'similar_patterns': similar_patterns,
    }
