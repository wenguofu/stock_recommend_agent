#!/usr/bin/env python3
"""Layer 2: 多信号评分"""
import sys
import os
import numpy as np
from typing import Dict, List

def score_layer2(layer1_result: Dict) -> Dict:
    """
    Layer 2: 对Layer 1候选股进行多信号加权评分

    Args:
        layer1_result: Layer 1的输出结果

    Returns:
        {
            'scored_candidates': [...],
            'top_candidates': [...],  # Top 20-30
            'recommendation_type': str
        }
    """
    from data_fetchers import get_daily_kline

    candidates = layer1_result.get('candidates', [])
    rec_type = layer1_result.get('recommendation_type', 'short')

    scored = []

    for cand in candidates:
        code = cand['code']
        try:
            # 获取日K线数据
            df = get_daily_kline(code, count=120)
            if df is None or len(df) < 60:
                continue

            close = df['close'].values.astype(float)
            high = df['high'].values.astype(float)
            low = df['low'].values.astype(float)
            open_p = df['open'].values.astype(float)
            volume = df['volume'].values.astype(float)

            n = len(close)

            # 计算各项信号
            if rec_type == 'short':
                signals = _calc_short_signals(close, high, low, open_p, volume)
            else:
                signals = _calc_mid_signals(close, high, low, volume)

            # 计算综合评分
            score = _calc_composite_score(signals, rec_type)

            signals['code'] = code
            signals['name'] = cand.get('name', '')
            signals['composite_score'] = score
            signals['rec_type'] = rec_type

            scored.append(signals)

        except Exception as e:
            continue

    # 按评分排序
    scored.sort(key=lambda x: x['composite_score'], reverse=True)

    # 取Top 20-30
    top_count = 30 if rec_type == 'short' else 20
    top_candidates = scored[:top_count]

    return {
        'scored_candidates': scored,
        'top_candidates': top_candidates,
        'total_candidates': len(scored),
        'recommendation_type': rec_type
    }


def _calc_short_signals(close, high, low, open_p, volume) -> Dict:
    """计算短线信号"""
    n = len(close)

    # 1. 突破20日高点
    high_20d = np.max(high[-21:-1])
    current_close = close[-1]
    breakout_pct = (current_close / high_20d - 1) * 100 if high_20d > 0 else 0
    breakout_score = 20 if breakout_pct > 5 else (16 if breakout_pct > 3 else (12 if breakout_pct > 0 else 0))

    # 2. 成交量放大
    avg_vol_20 = np.mean(volume[-21:-1])
    vol_ratio = volume[-1] / avg_vol_20 if avg_vol_20 > 0 else 1
    vol_score = 15 if vol_ratio > 3 else (12 if vol_ratio > 2 else (9 if vol_ratio > 1.5 else 3))

    # 3. 价格站上均线
    ma5 = np.mean(close[-5:])
    ma10 = np.mean(close[-10:])
    ma20 = np.mean(close[-20:])
    ma_count = sum([1 if current_close > ma5 else 0,
                    1 if current_close > ma10 else 0,
                    1 if current_close > ma20 else 0])
    ma_score = ma_count * 3.33  # 0-10分

    # 4. 均线多头 (MA5 > MA20)
    ma_cross_score = 15 if ma5 > ma20 else 0

    # 5. RSI
    rsi = _calc_rsi(close, 14)
    rsi_score = 10 if 50 <= rsi <= 60 else (8 if 40 <= rsi <= 70 else 4)

    # 6. 近10日最大回撤
    max_dd_10d = (np.max(close[-10:]) - current_close) / np.max(close[-10:]) * 100
    dd_score = 10 if max_dd_10d < 5 else (8 if max_dd_10d < 10 else 4)

    # 7. 资金信号（简化：量比变化）
    vol_ratio_3d = np.mean(volume[-3:]) / np.mean(volume[-6:-3]) if np.mean(volume[-6:-3]) > 0 else 1
    money_score = 15 if vol_ratio_3d > 1.2 else (8 if vol_ratio_3d > 1 else 0)

    return {
        'breakout_pct': round(breakout_pct, 2),
        'vol_ratio': round(vol_ratio, 2),
        'ma_count': ma_count,
        'rsi': round(rsi, 1),
        'max_dd_10d': round(max_dd_10d, 2),
        'vol_ratio_3d': round(vol_ratio_3d, 2),
        'breakout_score': breakout_score,
        'vol_score': vol_score,
        'ma_score': ma_score,
        'ma_cross_score': ma_cross_score,
        'rsi_score': rsi_score,
        'dd_score': dd_score,
        'money_score': money_score,
    }


def _calc_mid_signals(close, high, volume) -> Dict:
    """计算中线信号"""
    n = len(close)

    # 1. 均线多头 (MA10 > MA60)
    ma10 = np.mean(close[-10:])
    ma60 = np.mean(close[-60:]) if n >= 60 else close[-1]
    ma_cross_score = 20 if ma10 > ma60 else 0

    # 2. 60日涨幅
    ret60 = (close[-1] / close[-60] - 1) * 100 if n >= 60 else 0
    ret60_score = 15 if 40 <= ret60 <= 60 else (12 if 20 <= ret60 <= 80 else 6)

    # 3. 突破60日高点
    high_60d = np.max(high[-61:-1])
    breakout_pct = (close[-1] / high_60d - 1) * 100 if high_60d > 0 else 0
    breakout_score = 15 if breakout_pct > 10 else (12 if breakout_pct > 5 else 6)

    # 4. 成交量放大
    avg_vol_60 = np.mean(volume[-61:-1])
    vol_ratio = volume[-1] / avg_vol_60 if avg_vol_60 > 0 else 1
    vol_score = 10 if vol_ratio > 3 else (6 if vol_ratio > 2 else 3)

    # 波动率
    returns = np.diff(close[-21:]) / close[-21:-1]
    vol = float(np.std(returns) * 100 * np.sqrt(252))
    vol_score = 10 if 25 <= vol <= 50 else 5

    return {
        'ret60': round(ret60, 2),
        'breakout_pct': round(breakout_pct, 2),
        'vol_ratio': round(vol_ratio, 2),
        'ma_cross_score': ma_cross_score,
        'ret60_score': ret60_score,
        'breakout_score': breakout_score,
        'vol_score': vol_score,
    }


def _calc_rsi(close, period=14):
    """计算RSI"""
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.zeros(len(close))
    avg_loss = np.zeros(len(close))
    avg_gain[period] = np.mean(gains[:period])
    avg_loss[period] = np.mean(losses[:period])

    for i in range(period + 1, len(close)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period

    rs = avg_gain[-1] / avg_loss[-1] if avg_loss[-1] > 0 else 100
    return 100 - 100 / (1 + rs)


def _calc_composite_score(signals: Dict, rec_type: str) -> float:
    """计算综合评分"""
    if rec_type == 'short':
        weights = {
            'breakout_score': 0.20,
            'vol_score': 0.15,
            'ma_score': 0.10,
            'ma_cross_score': 0.15,
            'rsi_score': 0.10,
            'dd_score': 0.10,
            'money_score': 0.15,
        }
    else:
        weights = {
            'ma_cross_score': 0.20,
            'ret60_score': 0.15,
            'breakout_score': 0.15,
            'vol_score': 0.10,
        }

    score = 0
    for key, weight in weights.items():
        score += signals.get(key, 0) * weight

    return round(score, 1)