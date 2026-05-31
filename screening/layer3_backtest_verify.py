#!/usr/bin/env python3
"""Layer 3: 历史胜率验证"""
import sys
import os
import numpy as np
from typing import Dict, List, Tuple
from datetime import datetime

def verify_layer3(layer2_result: Dict) -> Dict:
    """
    Layer 3: 对Layer 2候选股进行历史胜率验证

    核心逻辑：
    1. 记录当前信号状态
    2. 在历史K线中搜索相同信号模式
    3. 统计出现相同信号后N日的上涨概率
    4. 只推荐：历史胜率 > 70% 的股票

    Args:
        layer2_result: Layer 2的输出结果

    Returns:
        {
            'verified_candidates': [...],
            'top_recommendations': [...],  # Top 3-5
            'recommendation_type': str
        }
    """
    top_candidates = layer2_result.get('top_candidates', [])
    rec_type = layer2_result.get('recommendation_type', 'short')

    verified = []

    for cand in top_candidates[:50]:  # 只验证Top 50，减少计算量
        code = cand['code']
        try:
            win_rates, avg_returns = _calculate_historical_win_rate(code, rec_type)

            if not win_rates:
                continue

            # 取关键周期的胜率
            key_period = '5d' if rec_type == 'short' else '20d'
            win_rate = win_rates.get(key_period, 0)
            avg_return = avg_returns.get(key_period, 0)

            # 只保留胜率 > 70% 的股票
            if win_rate >= 0.70:
                cand['win_rates'] = win_rates
                cand['avg_returns'] = avg_returns
                cand['key_win_rate'] = win_rate
                cand['key_avg_return'] = avg_return
                cand['sample_count'] = len(win_rates)

                # 计算目标价和止损价
                current_price = cand.get('close', cand.get('price', 0))
                if current_price > 0:
                    cand['target_price'] = round(current_price * (1 + avg_return / 100 * 2), 2)
                    cand['stop_loss_price'] = round(current_price * 0.93, 2)

                verified.append(cand)

        except Exception as e:
            continue

    # 按胜率排序
    verified.sort(key=lambda x: (x['key_win_rate'], x['composite_score']), reverse=True)

    # 取Top 3-5
    top_count = 5 if rec_type == 'short' else 3
    top_recommendations = verified[:top_count]

    return {
        'verified_candidates': verified,
        'top_recommendations': top_recommendations,
        'total_verified': len(verified),
        'recommendation_type': rec_type
    }


def _calculate_historical_win_rate(code: str, rec_type: str) -> Tuple[Dict, Dict]:
    """
    计算历史胜率

    对每只股票：
    1. 获取历史K线数据
    2. 在每个历史点检测是否出现"相同信号模式"
    3. 统计信号后5/10/20日的收益
    4. 返回各周期胜率和平均收益
    """
    from data_fetchers import get_daily_kline

    df = get_daily_kline(code, count=500)
    if df is None or len(df) < 120:
        return {}, {}

    close = df['close'].values.astype(float)
    high = df['high'].values.astype(float)
    volume = df['volume'].values.astype(float)

    n = len(close)

    win_counts = {'5d': 0, '10d': 0, '20d': 0}
    return_sums = {'5d': 0, '10d': 0, '20d': 0}
    signal_counts = {'5d': 0, '10d': 0, '20d': 0}

    hold_periods = {'5d': 5, '10d': 10, '20d': 20}

    # 从120天开始（确保有足够历史数据）
    for i in range(120, n - 20):
        # 检查是否满足信号条件
        if rec_type == 'short':
            signals_match = _check_short_signals(close, high, volume, i)
        else:
            signals_match = _check_mid_signals(close, high, volume, i)

        if not signals_match:
            continue

        # 计算后续各周期收益
        for period_key, hold_days in hold_periods.items():
            if i + hold_days < n:
                future_price = close[i + hold_days]
                current_price = close[i]
                ret = (future_price / current_price - 1) * 100

                signal_counts[period_key] += 1
                return_sums[period_key] += ret

                if ret > 0:
                    win_counts[period_key] += 1

    # 计算胜率和平均收益
    win_rates = {}
    avg_returns = {}

    for period in ['5d', '10d', '20d']:
        if signal_counts[period] >= 10:  # 至少10个样本
            win_rates[period] = round(win_counts[period] / signal_counts[period], 3)
            avg_returns[period] = round(return_sums[period] / signal_counts[period], 2)
        else:
            win_rates[period] = 0
            avg_returns[period] = 0

    return win_rates, avg_returns


def _check_short_signals(close, high, volume, idx) -> bool:
    """检查历史点是否满足短线信号条件"""
    if idx < 20:
        return False

    # 1. 突破20日高点
    high_20d = np.max(high[idx-21:idx])
    if close[idx] <= high_20d:
        return False

    # 2. 成交量放大
    avg_vol_20 = np.mean(volume[idx-21:idx])
    if avg_vol_20 <= 0 or volume[idx] / avg_vol_20 < 1.5:
        return False

    # 3. 价格站上均线
    ma20 = np.mean(close[idx-20:idx])
    if close[idx] <= ma20:
        return False

    # 4. RSI不超买
    rsi = _calc_rsi(close[idx-15:idx+1], 14)
    if rsi > 75:
        return False

    return True


def _check_mid_signals(close, high, volume, idx) -> bool:
    """检查历史点是否满足中线信号条件"""
    if idx < 60:
        return False

    # 1. MA10 > MA60
    ma10 = np.mean(close[idx-10:idx])
    ma60 = np.mean(close[idx-60:idx])
    if ma10 <= ma60:
        return False

    # 2. 60日涨幅20-80%
    ret60 = (close[idx] / close[idx-60] - 1) * 100
    if not (20 <= ret60 <= 80):
        return False

    # 3. 突破60日高点
    high_60d = np.max(high[idx-61:idx])
    if close[idx] <= high_60d:
        return False

    return True


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