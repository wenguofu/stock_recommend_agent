#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
组合优化模块 — 从单股分析升级为组合推荐

功能:
  - 相关性矩阵: 持仓+候选股的相关性
  - 均值-方差优化: 最小化风险 或 最大化夏普
  - 有效前沿: 风险-收益边界采样
  - 风险平价: 等风险贡献权重
  - 组合推荐引擎: 综合考虑持仓、候选、风险预算
"""

import traceback
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

import numpy as np
import pandas as pd

from data_fetchers import get_daily_kline


# ═══════════════════════════════════════════════════════════════
# 数据准备
# ═══════════════════════════════════════════════════════════════

def _get_returns_matrix(
    codes: List[str],
    days: int = 120,
) -> Tuple[pd.DataFrame, List[str]]:
    """
    获取多只股票的收益率矩阵

    Returns:
        (returns_df, valid_codes): returns_df行=日期, 列=代码; valid_codes成功的代码列表
    """
    price_dict = {}
    valid_codes = []

    for code in codes:
        try:
            kline = get_daily_kline(str(code).zfill(6), count=days + 5)
            if kline is not None and len(kline) >= 30:
                price_dict[code] = kline['close'].values.astype(float)
                valid_codes.append(code)
        except Exception:
            continue

    if len(valid_codes) < 2:
        return pd.DataFrame(), valid_codes

    # 对齐日期: 取最短长度
    min_len = min(len(p) for p in price_dict.values())
    aligned = {}
    for code in valid_codes:
        aligned[code] = price_dict[code][-min_len:]

    # 转成收益率
    returns_data = {}
    for code in valid_codes:
        prices = aligned[code]
        rets = np.diff(prices) / prices[:-1]
        returns_data[code] = rets

    returns_df = pd.DataFrame(returns_data)
    returns_df = returns_df.dropna()

    return returns_df, valid_codes


# ═══════════════════════════════════════════════════════════════
# 相关性矩阵
# ═══════════════════════════════════════════════════════════════

def calc_correlation_matrix(
    codes: List[str],
    days: int = 120,
) -> Dict:
    """
    计算股票池的相关性矩阵

    Args:
        codes: 股票代码列表
        days: 回看天数

    Returns:
        dict: {matrix: [[...]], labels: [...], avg_correlation, high_corr_pairs}
    """
    returns_df, valid_codes = _get_returns_matrix(codes, days)

    if len(valid_codes) < 2:
        return {
            'success': False,
            'error': f'有效股票数不足 ({len(valid_codes)} < 2)',
            'valid_codes': valid_codes,
        }

    corr_matrix = returns_df.corr()
    corr_matrix = corr_matrix.round(4)

    # 平均相关性
    n = len(valid_codes)
    if n > 1:
        upper_tri = corr_matrix.values[np.triu_indices(n, k=1)]
        avg_corr = float(np.mean(upper_tri))
    else:
        avg_corr = 1.0

    # 高相关对 (corr > 0.7)
    high_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            corr_val = corr_matrix.iloc[i, j]
            if corr_val > 0.7:
                high_pairs.append({
                    'pair': [valid_codes[i], valid_codes[j]],
                    'correlation': round(float(corr_val), 4),
                })

    return {
        'success': True,
        'matrix': corr_matrix.values.tolist(),
        'labels': valid_codes,
        'avg_correlation': round(avg_corr, 4),
        'high_corr_pairs': high_pairs,
        'correlation_level': _interpret_correlation(avg_corr),
        'days': days,
        'n_stocks': n,
    }


def _interpret_correlation(avg_corr: float) -> str:
    if avg_corr > 0.7:
        return '高度相关: 组合分散化效果差'
    elif avg_corr > 0.5:
        return '中度相关: 有一定分散化效果'
    elif avg_corr > 0.3:
        return '低度相关: 分散化效果较好'
    else:
        return '弱相关: 分散化效果很好'


# ═══════════════════════════════════════════════════════════════
# 均值-方差优化
# ═══════════════════════════════════════════════════════════════

def markowitz_optimize(
    codes: List[str],
    days: int = 120,
    target_return: Optional[float] = None,
    risk_free_rate: float = 0.02,
    max_weight: float = 0.40,
    min_weight: float = 0.0,
) -> Dict:
    """
    均值-方差组合优化

    使用 scipy.optimize 求解:
    - target_return=None: 最小方差组合 (MVP - Minimum Variance Portfolio)
    - target_return=value: 给定目标收益下的最小方差组合
    - 自动约束: sum(w) = 1, min_weight <= w_i <= max_weight

    Args:
        codes: 股票代码列表
        days: 回看天数
        target_return: 目标年化收益率 (如 0.15 = 15%)，None则求最小方差
        risk_free_rate: 无风险利率
        max_weight: 单只股票最大权重
        min_weight: 单只股票最小权重

    Returns:
        dict: {weights, portfolio_return, portfolio_vol, sharpe_ratio, ...}
    """
    returns_df, valid_codes = _get_returns_matrix(codes, days)

    if len(valid_codes) < 2:
        return {
            'success': False,
            'error': f'有效股票数不足 ({len(valid_codes)}), 无法优化',
            'valid_codes': valid_codes,
        }

    # 年化收益率和协方差
    mean_returns = returns_df.mean().values * 252
    cov_matrix = returns_df.cov().values * 252

    n = len(valid_codes)

    try:
        from scipy.optimize import minimize

        # 目标函数: 组合方差
        def portfolio_variance(weights):
            return weights @ cov_matrix @ weights

        # 约束: sum(w) = 1
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]

        # 如果指定目标收益, 添加收益约束
        if target_return is not None:
            constraints.append({
                'type': 'eq',
                'fun': lambda w, mr=mean_returns, tr=target_return: w @ mr - tr,
            })

        # 边界
        bounds = [(min_weight, max_weight) for _ in range(n)]

        # 初始猜测: 等权重
        initial_guess = np.ones(n) / n

        result = minimize(
            portfolio_variance,
            initial_guess,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-10},
        )

        if not result.success:
            return {
                'success': False,
                'error': f'优化未收敛: {result.message}',
                'valid_codes': valid_codes,
            }

        weights = result.x

        # 计算实际指标
        port_return = float(weights @ mean_returns)
        port_vol = float(math.sqrt(weights @ cov_matrix @ weights))
        sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0

        # 格式化为百分比
        allocations = []
        for i, code in enumerate(valid_codes):
            if weights[i] > 0.001:  # 过滤掉太小的权重
                allocations.append({
                    'code': code,
                    'weight_pct': round(float(weights[i]) * 100, 1),
                })

        allocations.sort(key=lambda x: x['weight_pct'], reverse=True)

        return {
            'success': True,
            'type': 'min_variance' if target_return is None else 'target_return',
            'target_return_annual': target_return,
            'allocations': allocations,
            'portfolio_return_annual_pct': round(port_return * 100, 2),
            'portfolio_volatility_annual_pct': round(port_vol * 100, 2),
            'sharpe_ratio': round(sharpe, 4),
            'risk_free_rate': risk_free_rate,
            'valid_codes': valid_codes,
            'n_stocks': n,
            'max_single_weight': max_weight,
        }

    except ImportError:
        # 无scipy时的降级方案: 等权重
        return _equal_weight_fallback(valid_codes, mean_returns, cov_matrix, risk_free_rate)


def _equal_weight_fallback(
    codes: List[str],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float,
) -> Dict:
    """等权重降级方案 (无scipy时)"""
    n = len(codes)
    weights = np.ones(n) / n
    port_return = float(weights @ mean_returns)
    port_vol = float(math.sqrt(weights @ cov_matrix @ weights))
    sharpe = (port_return - risk_free_rate) / port_vol if port_vol > 0 else 0

    return {
        'success': True,
        'type': 'equal_weight (fallback, scipy not available)',
        'allocations': [{'code': c, 'weight_pct': round(100.0 / n, 1)} for c in codes],
        'portfolio_return_annual_pct': round(port_return * 100, 2),
        'portfolio_volatility_annual_pct': round(port_vol * 100, 2),
        'sharpe_ratio': round(sharpe, 4),
        'valid_codes': codes,
        'n_stocks': n,
        'warning': 'scipy 不可用，使用等权重降级方案',
    }


# ═══════════════════════════════════════════════════════════════
# 有效前沿
# ═══════════════════════════════════════════════════════════════

def efficient_frontier(
    codes: List[str],
    days: int = 120,
    points: int = 20,
    risk_free_rate: float = 0.02,
) -> Dict:
    """
    计算有效前沿

    在最小方差组合和最大收益组合之间采样N个点

    Returns:
        dict: {frontier: [{return, vol, sharpe, weights}], mvp, max_sharpe}
    """
    returns_df, valid_codes = _get_returns_matrix(codes, days)

    if len(valid_codes) < 2:
        return {
            'success': False,
            'error': f'有效股票数不足 ({len(valid_codes)})',
            'valid_codes': valid_codes,
        }

    mean_returns = returns_df.mean().values * 252
    cov_matrix = returns_df.cov().values * 252
    n = len(valid_codes)

    try:
        from scipy.optimize import minimize

        # 先求最小方差组合和最大收益组合作为范围
        result_mvp = minimize(
            lambda w: w @ cov_matrix @ w,
            np.ones(n) / n,
            method='SLSQP',
            bounds=[(0, 0.40) for _ in range(n)],
            constraints=[{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}],
        )

        if not result_mvp.success:
            return {'success': False, 'error': 'MVP优化失败'}

        mvp_weights = result_mvp.x
        mvp_return = float(mvp_weights @ mean_returns)

        # 最大收益
        max_ret = float(np.max(mean_returns))
        min_ret = mvp_return

        # 如果最小方差组合收益已经是最大的, 调整范围
        if min_ret >= max_ret:
            min_ret = max_ret * 0.5

        # 采样
        target_returns = np.linspace(min_ret, max_ret * 0.95, points)
        frontier = []
        max_sharpe_point = None
        max_sharpe_val = -float('inf')

        for target in target_returns:
            result = minimize(
                lambda w: w @ cov_matrix @ w,
                np.ones(n) / n,
                method='SLSQP',
                bounds=[(0, 0.40) for _ in range(n)],
                constraints=[
                    {'type': 'eq', 'fun': lambda w: np.sum(w) - 1},
                    {'type': 'eq', 'fun': lambda w, t=target: w @ mean_returns - t},
                ],
                options={'maxiter': 500},
            )

            if result.success:
                w = result.x
                port_ret = float(w @ mean_returns)
                port_vol = float(math.sqrt(w @ cov_matrix @ w))
                sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 0 else 0

                allocations = [
                    {'code': valid_codes[i], 'weight_pct': round(float(w[i]) * 100, 1)}
                    for i in range(n) if w[i] > 0.005
                ]

                point = {
                    'return_annual_pct': round(port_ret * 100, 2),
                    'volatility_annual_pct': round(port_vol * 100, 2),
                    'sharpe_ratio': round(sharpe, 4),
                    'allocations': allocations,
                }
                frontier.append(point)

                if sharpe > max_sharpe_val:
                    max_sharpe_val = sharpe
                    max_sharpe_point = point

        # MVP
        mvp_vol = float(math.sqrt(mvp_weights @ cov_matrix @ mvp_weights))
        mvp_sharpe = (mvp_return - risk_free_rate) / mvp_vol if mvp_vol > 0 else 0
        mvp_point = {
            'return_annual_pct': round(mvp_return * 100, 2),
            'volatility_annual_pct': round(mvp_vol * 100, 2),
            'sharpe_ratio': round(mvp_sharpe, 4),
            'allocations': [
                {'code': valid_codes[i], 'weight_pct': round(float(mvp_weights[i]) * 100, 1)}
                for i in range(n) if mvp_weights[i] > 0.005
            ],
        }

        return {
            'success': True,
            'frontier': frontier,
            'mvp': mvp_point,  # 最小方差组合
            'max_sharpe': max_sharpe_point,  # 最大夏普组合
            'n_points': len(frontier),
            'valid_codes': valid_codes,
            'n_stocks': n,
        }

    except ImportError:
        return {
            'success': False,
            'error': 'scipy 不可用，无法计算有效前沿',
            'valid_codes': valid_codes,
        }


# ═══════════════════════════════════════════════════════════════
# 风险平价
# ═══════════════════════════════════════════════════════════════

def risk_parity(
    codes: List[str],
    days: int = 120,
    max_weight: float = 0.40,
) -> Dict:
    """
    风险平价: 使每只股票对组合的风险贡献相等

    Returns:
        dict: {allocations, portfolio_vol, risk_contributions}
    """
    returns_df, valid_codes = _get_returns_matrix(codes, days)

    if len(valid_codes) < 2:
        return {
            'success': False,
            'error': f'有效股票数不足 ({len(valid_codes)})',
            'valid_codes': valid_codes,
        }

    cov_matrix = returns_df.cov().values * 252
    n = len(valid_codes)

    try:
        from scipy.optimize import minimize

        def risk_contribution(weights):
            """每只股票的风险贡献"""
            port_vol = math.sqrt(weights @ cov_matrix @ weights)
            # MRC = cov @ weights / port_vol
            mrc = cov_matrix @ weights / port_vol
            # RC = weights * MRC
            rc = weights * mrc
            return rc / port_vol  # 归一化

        def objective(weights):
            """目标: 风险贡献方差最小化"""
            rc = risk_contribution(weights)
            target = np.ones(n) / n
            return np.sum((rc - target) ** 2)

        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1}]
        bounds = [(0.01, max_weight) for _ in range(n)]
        initial = np.ones(n) / n

        result = minimize(
            objective, initial,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-10},
        )

        if not result.success:
            return {'success': False, 'error': f'风险平价优化未收敛: {result.message}'}

        weights = result.x
        port_vol = float(math.sqrt(weights @ cov_matrix @ weights))
        rc = risk_contribution(weights)

        allocations = [
            {
                'code': valid_codes[i],
                'weight_pct': round(float(weights[i]) * 100, 1),
                'risk_contribution_pct': round(float(rc[i]) * 100, 1),
            }
            for i in range(n) if weights[i] > 0.005
        ]

        return {
            'success': True,
            'allocations': allocations,
            'portfolio_volatility_annual_pct': round(port_vol * 100, 2),
            'risk_balance_score': round(float(1 - np.std(rc) * n), 4),
            'valid_codes': valid_codes,
        }

    except ImportError:
        return {
            'success': False,
            'error': 'scipy 不可用',
            'valid_codes': valid_codes,
        }


# ═══════════════════════════════════════════════════════════════
# 组合推荐引擎
# ═══════════════════════════════════════════════════════════════

def recommend_portfolio(
    holdings: List[Dict],       # [{'code': '300679', 'shares': 200, 'cost': 55.51}]
    candidates: List[str],       # ['300433', '603290', ...]
    total_capital: float,        # 总资金
    days: int = 120,
    max_stocks: int = 5,
    risk_profile: str = 'moderate',  # 'conservative', 'moderate', 'aggressive'
) -> Dict:
    """
    组合推荐引擎

    综合考虑: 现有持仓 + 候选股 + 风险预算

    Steps:
    1. 获取所有股票(持仓+候选)的收益率矩阵
    2. 计算相关性, 过滤高度相关的冗余候选
    3. 均值-方差优化得到权重
    4. 使用凯利公式调整仓位
    5. 计算每只股票的止损价

    Args:
        holdings: 现有持仓列表
        candidates: 候选股票代码
        total_capital: 总资金
        days: 回看天数
        max_stocks: 最大持股数
        risk_profile: 风险偏好 (conservative/moderate/aggressive)

    Returns:
        dict: 完整的组合推荐
    """
    holding_codes = [h['code'] for h in holdings]

    # 风险预算
    risk_budgets = {
        'conservative': {'max_total_risk_pct': 10, 'max_single_weight': 0.25, 'min_cash': 0.20},
        'moderate': {'max_total_risk_pct': 20, 'max_single_weight': 0.35, 'min_cash': 0.10},
        'aggressive': {'max_total_risk_pct': 30, 'max_single_weight': 0.50, 'min_cash': 0.05},
    }
    budget = risk_budgets.get(risk_profile, risk_budgets['moderate'])

    # 1. 计算相关性矩阵, 去冗余
    all_codes = holding_codes + candidates
    corr_result = calc_correlation_matrix(all_codes, days)

    if not corr_result.get('success'):
        return {
            'success': False,
            'error': '相关性计算失败',
            'detail': corr_result.get('error', 'unknown'),
        }

    # 保留相关性<0.7的候选股 (与持仓不太重复)
    filtered_candidates = []
    for c in candidates:
        is_redundant = False
        for h_code in holding_codes:
            if c in corr_result['labels'] and h_code in corr_result['labels']:
                i = corr_result['labels'].index(h_code)
                j = corr_result['labels'].index(c)
                corr_val = corr_result['matrix'][i][j]
                if corr_val > 0.75:
                    is_redundant = True
                    break
        if not is_redundant:
            filtered_candidates.append(c)

    # 与持仓合并
    optimized_codes = holding_codes + filtered_candidates[:max(0, max_stocks - len(holding_codes))]

    if len(optimized_codes) < 1:
        return {'success': False, 'error': '无有效股票'}

    # 2. 均值-方差优化
    opt_result = markowitz_optimize(
        optimized_codes, days,
        max_weight=budget['max_single_weight'],
    )

    if not opt_result.get('success'):
        return {
            'success': False,
            'error': '组合优化失败',
            'detail': opt_result.get('error', 'unknown'),
        }

    # 3. 计算每只股票的建议
    import math as _math
    from data_fetchers import get_daily_kline

    recommendations = []
    total_weight = 0
    for alloc in opt_result['allocations']:
        code = alloc['code']
        weight = alloc['weight_pct'] / 100
        total_weight += weight

        # 实际金额
        amount = total_capital * weight

        # 凯利仓位
        try:
            from risk_management import _estimate_kelly_from_data
            kline = get_daily_kline(str(code).zfill(6), count=days)
            if kline is not None:
                prices = kline['close'].values.astype(float)
                returns = np.diff(prices) / prices[:-1]
                returns = returns[~np.isnan(returns)]
                kelly = _estimate_kelly_from_data(code, returns)
            else:
                kelly = {'is_valid': False}
        except Exception:
            kelly = {'is_valid': False}

        # 当前价格
        try:
            kline = get_daily_kline(str(code).zfill(6), count=5)
            current_price = float(kline['close'].values[-1]) if kline is not None else 0
        except Exception:
            current_price = 0

        # 建议股数
        shares = int(amount / current_price / 100) * 100 if current_price > 0 else 0

        # ATR止损
        try:
            from risk_management import calc_atr_stop_loss
            kline_full = get_daily_kline(str(code).zfill(6), count=days)
            atr = calc_atr_stop_loss(kline_full) if kline_full is not None else {}
            stop_loss = atr.get('stop_loss_price')
        except Exception:
            stop_loss = None

        rec = {
            'code': code,
            'weight_pct': alloc['weight_pct'],
            'amount': round(amount, 2),
            'shares': shares,
            'current_price': round(current_price, 2),
            'stop_loss': stop_loss,
        }

        if kelly.get('is_valid'):
            rec['kelly_pct'] = kelly.get('fractional_pct')
            rec['kelly_level'] = kelly.get('risk_level')

        recommendations.append(rec)

    # 现金比例
    cash_pct = max(0, 1 - total_weight)
    cash_amount = total_capital * cash_pct

    return {
        'success': True,
        'risk_profile': risk_profile,
        'total_capital': total_capital,
        'recommendations': recommendations,
        'cash_pct': round(cash_pct * 100, 1),
        'cash_amount': round(cash_amount, 2),
        'portfolio_return_annual_pct': opt_result.get('portfolio_return_annual_pct'),
        'portfolio_volatility_annual_pct': opt_result.get('portfolio_volatility_annual_pct'),
        'sharpe_ratio': opt_result.get('sharpe_ratio'),
        'correlation': {
            'avg_correlation': corr_result.get('avg_correlation'),
            'level': corr_result.get('correlation_level'),
        },
        'max_single_weight_pct': round(budget['max_single_weight'] * 100),
        'filtered_out': [c for c in candidates if c not in optimized_codes],
    }
