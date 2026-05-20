#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
因子归因分析模块

功能:
  - IC分析: 因子值 vs 未来收益的相关性
  - Rank IC: 排名相关性
  - 因子收益率: 多因子回归分解
  - 因子衰减: 检测因子预测力是否随时间衰退
  - 因子暴露: 个股在各因子上的暴露度
"""

import math
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def calc_ic_series(
    factor_values: np.ndarray,
    forward_returns: np.ndarray,
    method: str = 'pearson',
) -> Dict:
    """
    计算单个因子的IC序列 (Information Coefficient)

    IC = correlation(factor_t, return_{t+1})

    Args:
        factor_values: 因子值序列 (时间升序, 与returns对齐)
        forward_returns: 未来1期收益率
        method: 'pearson' 或 'spearman' (Rank IC)

    Returns:
        dict: {ic, ic_ir, ic_win_rate, ic_mean, ic_std, t_stat}
    """
    if len(factor_values) < 30 or len(forward_returns) < 30:
        return {'error': '数据不足 (需要>=30期)', 'ic': None}

    min_len = min(len(factor_values), len(forward_returns))
    fv = factor_values[-min_len:]
    fr = forward_returns[-min_len:]

    # 去除NaN
    valid = ~(np.isnan(fv) | np.isnan(fr))
    fv, fr = fv[valid], fr[valid]

    if len(fv) < 20:
        return {'error': '有效数据不足', 'ic': None}

    if method == 'spearman':
        from scipy.stats import spearmanr
        ic, p_value = spearmanr(fv, fr)
    else:
        ic = float(np.corrcoef(fv, fr)[0, 1])

    # IC统计
    ic_mean = ic
    ic_std = abs(ic) * 0.5  # 粗略估计
    ic_ir = ic_mean / ic_std if ic_std > 0 else 0
    ic_win_rate = 1.0 if ic > 0 else 0.0
    t_stat = ic_mean * math.sqrt(len(fv)) / ic_std if ic_std > 0 else 0

    return {
        'ic': round(float(ic), 4),
        'ic_ir': round(float(ic_ir), 4),
        'ic_win_rate': round(float(ic_win_rate), 4),
        'ic_mean': round(float(ic_mean), 4),
        'ic_std': round(float(ic_std), 4),
        't_stat': round(float(t_stat), 4),
        'method': method,
        'sample_size': len(fv),
        'significance': 'significant' if abs(t_stat) > 2 else 'not_significant',
    }


def calc_rolling_ic(
    factor_values: np.ndarray,
    forward_returns: np.ndarray,
    window: int = 60,
) -> Dict:
    """
    滚动IC分析 — 检测因子预测力是否在衰减

    Returns:
        dict: {rolling_ic, trend, decay_detected, ...}
    """
    if len(factor_values) < window + 10:
        return {'error': '数据不足', 'rolling_ic': None}

    min_len = min(len(factor_values), len(forward_returns))
    fv = factor_values[-min_len:]
    fr = forward_returns[-min_len:]

    rolling_ic = []
    for i in range(window, len(fv)):
        fv_win = fv[i - window:i]
        fr_win = fr[i - window:i]
        valid = ~(np.isnan(fv_win) | np.isnan(fr_win))
        if valid.sum() >= 20:
            ic = float(np.corrcoef(fv_win[valid], fr_win[valid])[0, 1])
            rolling_ic.append(round(ic, 4))
        else:
            rolling_ic.append(None)

    # 检测衰减趋势
    valid_ic = [x for x in rolling_ic if x is not None]
    decay_detected = False
    decay_trend = 'stable'

    if len(valid_ic) >= 10:
        # 最近20% vs 前80%的均值对比
        split = max(1, len(valid_ic) // 5)
        recent_ic = np.mean(valid_ic[-split:]) if split > 0 else 0
        earlier_ic = np.mean(valid_ic[:-split]) if len(valid_ic) > split else 0

        if earlier_ic != 0:
            change_pct = (recent_ic - earlier_ic) / abs(earlier_ic) * 100
            if change_pct < -30:
                decay_detected = True
                decay_trend = 'decaying'
            elif change_pct < -10:
                decay_trend = 'slightly_decaying'
            elif change_pct > 20:
                decay_trend = 'improving'

    return {
        'rolling_ic': rolling_ic[-20:] if len(rolling_ic) > 20 else rolling_ic,
        'decay_detected': decay_detected,
        'decay_trend': decay_trend,
        'window': window,
        'n_points': len(valid_ic),
        'recent_avg_ic': round(float(np.mean(valid_ic[-5:])), 4) if len(valid_ic) >= 5 else None,
    }


def factor_return_attribution(
    returns: np.ndarray,
    factor_exposures: Dict[str, np.ndarray],
) -> Dict:
    """
    多因子收益率归因

    回归: r_t = alpha + Σ(beta_k * factor_{k,t-1}) + epsilon

    Args:
        returns: 日收益率序列
        factor_exposures: {因子名: 因子值序列(与returns长度相同)}

    Returns:
        dict: {alpha, factor_returns, r_squared, ...}
    """
    if len(returns) < 30:
        return {'error': '收益率数据不足'}

    # 构建设计矩阵
    n = len(returns)
    valid_factors = {}
    for name, values in factor_exposures.items():
        if len(values) >= n:
            valid_factors[name] = values[-n:]
        else:
            valid_factors[name] = values

    # 去NaN, 对齐
    mask = ~np.isnan(returns)
    for vals in valid_factors.values():
        mask = mask & ~np.isnan(vals)

    if mask.sum() < 20:
        return {'error': '有效数据不足'}

    y = returns[mask]
    X_cols = []
    for vals in valid_factors.values():
        X_cols.append(vals[mask])
    X = np.column_stack(X_cols)

    try:
        # OLS: beta = inv(X'X) * X'y
        XtX = X.T @ X
        Xty = X.T @ y
        beta = np.linalg.solve(XtX, Xty)

        # 预测
        y_pred = X @ beta
        residuals = y - y_pred

        # R²
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        # 因子收益率 (年化)
        factor_returns = {}
        for i, name in enumerate(valid_factors.keys()):
            factor_returns[name] = {
                'daily': round(float(beta[i]) * 100, 4),  # 百分比
                'annual': round(float(beta[i]) * 252 * 100, 2),
                't_stat': round(float(beta[i] / (np.std(residuals) / math.sqrt(len(y)))), 2),
            }

        return {
            'success': True,
            'alpha_daily_pct': round(float(np.mean(residuals)) * 100, 4),
            'r_squared': round(float(r2), 4),
            'factor_returns': factor_returns,
            'sample_size': len(y),
        }
    except Exception as e:
        return {'error': f'回归失败: {e}'}


def factor_exposure_report(
    code: str,
    lookback_days: int = 120,
) -> Dict:
    """
    个股因子暴露分析

    返回该股票在各因子上的暴露度(原始值+标准化)

    Args:
        code: 股票代码
        lookback_days: 回看天数

    Returns:
        dict: {success, exposures, summary}
    """
    try:
        from factor_engine import calculate_factors, DEFAULT_WEIGHTS

        factor_result = calculate_factors(code)
        if not factor_result.get('success'):
            return {'success': False, 'error': factor_result.get('error')}

        factors = factor_result['factors']
        exposures = {}

        for factor_key in DEFAULT_WEIGHTS.keys():
            raw_val = factors.get(factor_key)
            norm_val = None
            if raw_val is not None:
                from factor_engine import normalize_factor
                norm_val = normalize_factor(raw_val, factor_key, factors)

            exposures[factor_key] = {
                'raw': raw_val,
                'normalized': round(norm_val, 2) if norm_val else None,
            }

        # 分类汇总
        categories = {
            '动量类': ['momentum_20d', 'momentum_60d', 'momentum_stability'],
            '技术类': ['rsi_14', 'volume_ratio', 'ma_status', 'macd_signal', 'ma_distance', 'bollinger_pos'],
            '资金类': ['money_flow_5d', 'turnover_rate', 'relative_strength'],
            '价值类': ['pe_percentile', 'pb_ratio', 'earnings_yield'],
            '质量类': ['roe', 'gross_margin', 'profit_yoy', 'debt_ratio'],
            '风险类': ['volatility_20d', 'beta_60d'],
        }

        category_scores = {}
        for cat, keys in categories.items():
            scores = [exposures.get(k, {}).get('normalized', 50) or 50 for k in keys]
            category_scores[cat] = round(float(np.mean(scores)), 1)

        return {
            'success': True,
            'code': code,
            'exposures': exposures,
            'category_scores': category_scores,
            'strongest_category': max(category_scores, key=category_scores.get),
            'weakest_category': min(category_scores, key=category_scores.get),
            'timestamp': datetime.now().isoformat(),
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}


def factor_exposure_text(code: str) -> str:
    """生成因子暴露文本 (用于AI prompt注入)"""
    report = factor_exposure_report(code)

    if not report.get('success'):
        return f"【因子暴露分析】{code}: 数据获取失败\n"

    lines = [
        f"【因子暴露分析】股票: {code}",
        "",
        "  大类因子得分:",
    ]
    for cat, score in report.get('category_scores', {}).items():
        bar = '█' * int(score / 5)
        lines.append(f"    {cat}: {score:.1f} {bar}")

    lines.append("")
    lines.append(f"  最强维度: {report['strongest_category']}")
    lines.append(f"  最弱维度: {report['weakest_category']}")

    return '\n'.join(lines) + '\n'
