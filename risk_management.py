#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
风险管理模块 — 为量化推荐系统提供风险度量和仓位管理

功能:
  - VaR (Value at Risk): 历史法 / 参数法
  - CVaR (条件VaR): 尾部期望损失
  - 最大回撤 (Max Drawdown)
  - 夏普比率 (Sharpe Ratio)
  - 凯利公式仓位 (Kelly Criterion)
  - ATR动态止损
  - 贝塔系数 (vs 基准)
  - 综合风险报告
"""

import traceback
import math
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

import numpy as np
import pandas as pd

from data_fetchers import get_daily_kline
from utils import is_us_stock


# ═══════════════════════════════════════════════════════════════
# VaR 计算
# ═══════════════════════════════════════════════════════════════

def calc_var_historical(
    prices: np.ndarray,
    confidence: float = 0.95,
    horizon: int = 1,
    position_value: float = 1.0,
) -> Dict:
    """
    历史模拟法 VaR

    Args:
        prices: 价格序列 (np.ndarray, 按时间升序)
        confidence: 置信水平 (默认95%)
        horizon: 持有期 (天)
        position_value: 持仓市值

    Returns:
        dict: {var_amount, var_pct, confidence, horizon, method: 'historical'}
    """
    if len(prices) < 30:
        return {
            'var_amount': None,
            'var_pct': None,
            'error': f'数据不足 ({len(prices)}条, 需要≥30)',
            'confidence': confidence,
            'horizon': horizon,
            'method': 'historical',
        }

    # 日收益率
    returns = np.diff(prices) / prices[:-1]
    returns = returns[~np.isnan(returns)]

    if len(returns) < 20:
        return {
            'var_amount': None,
            'var_pct': None,
            'error': f'有效收益率不足 ({len(returns)}条)',
            'confidence': confidence,
            'horizon': horizon,
            'method': 'historical',
        }

    # 分位数
    alpha = 1 - confidence
    var_daily_pct = float(np.percentile(returns, alpha * 100))

    # 扩展到持有期 (假设独立同分布)
    var_horizon_pct = var_daily_pct * math.sqrt(horizon)
    var_amount = abs(var_horizon_pct) * position_value

    return {
        'var_amount': round(var_amount, 2),
        'var_pct': round(abs(var_horizon_pct) * 100, 2),
        'confidence': confidence,
        'horizon': horizon,
        'method': 'historical',
        'daily_var_pct': round(abs(var_daily_pct) * 100, 2),
        'sample_size': len(returns),
    }


def calc_var_parametric(
    returns: np.ndarray,
    confidence: float = 0.95,
    position_value: float = 1.0,
) -> Dict:
    """
    参数法 VaR (假设正态分布)

    Args:
        returns: 日收益率序列
        confidence: 置信水平
        position_value: 持仓市值

    Returns:
        dict: {var_amount, var_pct, ...}
    """
    if len(returns) < 20:
        return {
            'var_amount': None,
            'var_pct': None,
            'error': '收益率序列不足',
            'method': 'parametric',
        }

    mu = np.nanmean(returns)
    sigma = np.nanstd(returns)

    from scipy.stats import norm
    z_score = norm.ppf(1 - confidence)

    # VaR = -(mu + z * sigma) * position_value
    var_pct = -(mu + z_score * sigma)
    var_amount = var_pct * position_value

    return {
        'var_amount': round(abs(var_amount), 2),
        'var_pct': round(abs(var_pct) * 100, 2),
        'confidence': confidence,
        'method': 'parametric',
        'mu': round(mu * 100, 4),
        'sigma': round(sigma * 100, 4),
    }


def calc_cvar(
    prices: np.ndarray,
    confidence: float = 0.95,
    position_value: float = 1.0,
) -> Dict:
    """
    条件VaR (CVaR / Expected Shortfall)
    - 超过VaR阈值的平均损失

    Args:
        prices: 价格序列
        confidence: 置信水平
        position_value: 持仓市值

    Returns:
        dict: {cvar_amount, cvar_pct, var_at_threshold, ...}
    """
    if len(prices) < 30:
        return {
            'cvar_amount': None,
            'cvar_pct': None,
            'error': '数据不足',
        }

    returns = np.diff(prices) / prices[:-1]
    returns = returns[~np.isnan(returns)]

    if len(returns) < 20:
        return {'cvar_amount': None, 'cvar_pct': None, 'error': '有效收益率不足'}

    alpha = 1 - confidence
    var_threshold = np.percentile(returns, alpha * 100)

    # CVaR = 超过VaR阈值的均值损失
    tail_returns = returns[returns <= var_threshold]
    cvar_daily = np.mean(tail_returns) if len(tail_returns) > 0 else var_threshold

    cvar_amount = abs(cvar_daily) * position_value

    return {
        'cvar_amount': round(cvar_amount, 2),
        'cvar_pct': round(abs(cvar_daily) * 100, 2),
        'var_threshold_pct': round(abs(var_threshold) * 100, 2),
        'tail_samples': len(tail_returns),
        'confidence': confidence,
        'method': 'historical_cvar',
    }


# ═══════════════════════════════════════════════════════════════
# 回撤计算
# ═══════════════════════════════════════════════════════════════

def calc_max_drawdown(prices: np.ndarray) -> Dict:
    """
    计算最大回撤

    Args:
        prices: 价格序列

    Returns:
        dict: {max_drawdown_pct, max_drawdown_amount, peak_idx, trough_idx, peak_price, trough_price}
    """
    if len(prices) < 2:
        return {'max_drawdown_pct': 0, 'max_drawdown_amount': 0, 'error': '数据不足'}

    peak = prices[0]
    max_dd_pct = 0
    max_dd_amount = 0
    peak_idx = 0
    trough_idx = 0
    current_peak_idx = 0

    for i in range(1, len(prices)):
        if prices[i] > peak:
            peak = prices[i]
            current_peak_idx = i
        else:
            dd_pct = (peak - prices[i]) / peak
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
                max_dd_amount = peak - prices[i]
                peak_idx = current_peak_idx
                trough_idx = i

    return {
        'max_drawdown_pct': round(max_dd_pct * 100, 2),
        'max_drawdown_amount': round(max_dd_amount, 2),
        'peak_idx': int(peak_idx),
        'trough_idx': int(trough_idx),
        'peak_price': round(float(prices[peak_idx]), 2) if peak_idx < len(prices) else None,
        'trough_price': round(float(prices[trough_idx]), 2) if trough_idx < len(prices) else None,
    }


# ═══════════════════════════════════════════════════════════════
# 夏普比率
# ═══════════════════════════════════════════════════════════════

def calc_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.02,
    annualize: bool = True,
) -> Dict:
    """
    计算夏普比率

    Args:
        returns: 日收益率序列
        risk_free_rate: 无风险利率 (默认2%)
        annualize: 是否年化

    Returns:
        dict: {sharpe_ratio, annual_return, annual_volatility}
    """
    if len(returns) < 20:
        return {'sharpe_ratio': None, 'error': '收益率序列不足'}

    returns = returns[~np.isnan(returns)]
    mu_daily = np.nanmean(returns)
    sigma_daily = np.nanstd(returns)

    if sigma_daily == 0:
        return {'sharpe_ratio': 0, 'annual_return': 0, 'annual_volatility': 0}

    # 年化
    annual_return = mu_daily * 252
    annual_vol = sigma_daily * math.sqrt(252)
    daily_rf = risk_free_rate / 252

    sharpe = (mu_daily - daily_rf) / sigma_daily
    sharpe_annual = sharpe * math.sqrt(252) if annualize else sharpe

    return {
        'sharpe_ratio': round(sharpe_annual, 4) if annualize else round(sharpe, 4),
        'annual_return_pct': round(annual_return * 100, 2),
        'annual_volatility_pct': round(annual_vol * 100, 2),
        'risk_free_rate': risk_free_rate,
    }


# ═══════════════════════════════════════════════════════════════
# 凯利公式
# ═══════════════════════════════════════════════════════════════

def calc_kelly_position(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    fractional: float = 0.5,
) -> Dict:
    """
    凯利公式最优仓位

    f* = (p * W - q * L) / (W * L)
    其中: p=胜率, q=败率(1-p), W=平均盈利%, L=平均亏损%

    Args:
        win_rate: 胜率 (0-1)
        avg_win_pct: 平均盈利百分比 (如 5.0 表示5%)
        avg_loss_pct: 平均亏损百分比 (如 3.0 表示3%, 取正数)
        fractional: 分数凯利比例 (默认0.5=半凯利, 更保守)

    Returns:
        dict: {kelly_pct, fractional_pct, is_valid, explanation}
    """
    # 参数验证
    if avg_loss_pct <= 0:
        return {
            'kelly_pct': 0,
            'fractional_pct': 0,
            'is_valid': False,
            'explanation': '平均亏损必须 > 0',
        }
    if win_rate <= 0 or win_rate > 1:
        return {
            'kelly_pct': 0,
            'fractional_pct': 0,
            'is_valid': False,
            'explanation': '胜率必须在 0-1 之间',
        }

    loss_rate = 1 - win_rate

    # 凯利公式
    b = avg_win_pct / avg_loss_pct  # 盈亏比
    kelly = (win_rate * b - loss_rate) / b

    # 夹到 [0, 1]
    kelly = max(0, min(kelly, 1.0))

    fractional_kelly = kelly * fractional

    # 人性化解释
    if kelly >= 0.30:
        level = '积极'
    elif kelly >= 0.15:
        level = '适中'
    elif kelly >= 0.05:
        level = '保守'
    else:
        level = '不建议'

    return {
        'kelly_pct': round(kelly * 100, 1),
        'fractional_pct': round(fractional_kelly * 100, 1),
        'is_valid': True,
        'risk_level': level,
        'win_rate': round(win_rate * 100, 1),
        'avg_win_pct': round(avg_win_pct, 2),
        'avg_loss_pct': round(avg_loss_pct, 2),
        'profit_loss_ratio': round(b, 2),
        'fractional_factor': fractional,
    }


# ═══════════════════════════════════════════════════════════════
# ATR 止损
# ═══════════════════════════════════════════════════════════════

def calc_atr_stop_loss(
    df: pd.DataFrame,
    multiplier: float = 2.0,
    direction: str = 'long',
) -> Dict:
    """
    基于 ATR 的动态止损价

    ATR = max(high-low, abs(high-prev_close), abs(low-prev_close)) 的 N 日平均

    Args:
        df: DataFrame with columns [open, high, low, close]
        multiplier: ATR倍数 (默认2.0)
        direction: 'long' 或 'short'

    Returns:
        dict: {stop_loss_price, atr_value, atr_pct, multiplier}
    """
    if df is None or len(df) < 15:
        return {'stop_loss_price': None, 'error': '数据不足'}

    try:
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        # True Range
        tr = np.zeros(len(high))
        tr[0] = high[0] - low[0]
        for i in range(1, len(high)):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )

        # ATR = 14日EMA of TR
        atr_period = 14
        atr = np.zeros(len(tr))
        atr[atr_period - 1] = np.mean(tr[:atr_period])
        multiplier_ema = 2.0 / (atr_period + 1)
        for i in range(atr_period, len(tr)):
            atr[i] = (tr[i] - atr[i - 1]) * multiplier_ema + atr[i - 1]

        current_atr = atr[-1]
        current_close = close[-1]

        if direction == 'long':
            stop_price = current_close - multiplier * current_atr
        else:
            stop_price = current_close + multiplier * current_atr

        stop_price = max(stop_price, current_close * 0.5)  # 不低于半价

        return {
            'stop_loss_price': round(float(stop_price), 2),
            'atr_value': round(float(current_atr), 2),
            'atr_pct': round(float(current_atr / current_close * 100), 2),
            'multiplier': multiplier,
            'current_price': round(float(current_close), 2),
            'stop_loss_pct': round(float((current_close - stop_price) / current_close * 100), 2),
            'direction': direction,
        }
    except Exception as e:
        return {'stop_loss_price': None, 'error': str(e)}


# ═══════════════════════════════════════════════════════════════
# 贝塔系数
# ═══════════════════════════════════════════════════════════════

def calc_portfolio_beta(
    portfolio_returns: np.ndarray,
    benchmark_returns: np.ndarray,
) -> Dict:
    """
    计算组合贝塔 (相对于基准)

    Args:
        portfolio_returns: 组合日收益率
        benchmark_returns: 基准日收益率 (如沪深300)

    Returns:
        dict: {beta, alpha, r_squared, correlation}
    """
    if len(portfolio_returns) < 20 or len(benchmark_returns) < 20:
        return {'beta': None, 'error': '数据不足'}

    # 对齐长度
    min_len = min(len(portfolio_returns), len(benchmark_returns))
    pr = portfolio_returns[-min_len:]
    br = benchmark_returns[-min_len:]

    # 去除NaN
    valid = ~(np.isnan(pr) | np.isnan(br))
    pr = pr[valid]
    br = br[valid]

    if len(pr) < 20:
        return {'beta': None, 'error': '有效数据不足'}

    # Beta = Cov(r_p, r_b) / Var(r_b)
    cov = np.cov(pr, br)[0, 1]
    var_benchmark = np.var(br)

    if var_benchmark == 0:
        return {'beta': 0, 'alpha': 0, 'error': '基准无波动'}

    beta = cov / var_benchmark

    # Alpha = mean(r_p) - beta * mean(r_b)
    alpha = np.mean(pr) - beta * np.mean(br)
    alpha_annual = alpha * 252

    # R²
    corr = np.corrcoef(pr, br)[0, 1]
    r_squared = corr ** 2

    return {
        'beta': round(float(beta), 4),
        'alpha_annual_pct': round(float(alpha_annual) * 100, 2),
        'r_squared': round(float(r_squared), 4),
        'correlation': round(float(corr), 4),
        'interpretation': _interpret_beta(beta),
    }


def _interpret_beta(beta: float) -> str:
    if beta > 1.5:
        return '高波动: 比大盘波动大50%以上'
    elif beta > 1.1:
        return '偏进攻: 比大盘略活跃'
    elif beta > 0.9:
        return '与大盘同步'
    elif beta > 0.5:
        return '偏防御: 比大盘稳定'
    elif beta > 0:
        return '低波动: 与大盘关联弱'
    else:
        return '反向: 与大盘负相关'


# ═══════════════════════════════════════════════════════════════
# 综合风险报告
# ═══════════════════════════════════════════════════════════════

def risk_report(
    code: str,
    position: Optional[Dict] = None,
    lookback_days: int = 120,
) -> Dict:
    """
    生成单只股票的综合风险报告

    Args:
        code: 股票代码 (如 '300679')
        position: 持仓信息 {'shares': 200, 'cost': 55.51} 或 None
        lookback_days: 回看天数

    Returns:
        dict: 完整风险报告
    """
    report = {
        'code': code,
        'generated_at': datetime.now().isoformat(),
        'lookback_days': lookback_days,
        'position': position,
        'risk_grade': 'unknown',
        'errors': [],
    }

    # 1. 获取K线数据
    try:
        kline = get_daily_kline(code, count=lookback_days + 30)
        if kline is None or len(kline) < 30:
            report['errors'].append('K线数据不足')
            report['risk_grade'] = 'data_insufficient'
            return report

        prices = kline['close'].values.astype(float)
        returns = np.diff(prices) / prices[:-1]
        returns = returns[~np.isnan(returns)]

        current_price = prices[-1]
        report['current_price'] = round(float(current_price), 2)
    except Exception as e:
        report['errors'].append(f'数据获取失败: {e}')
        report['risk_grade'] = 'data_error'
        return report

    # 2. VaR (历史法, 95%)
    var_result = calc_var_historical(prices, confidence=0.95)
    report['var_95'] = var_result

    # 3. VaR (参数法, 95%)
    var_param = calc_var_parametric(returns, confidence=0.95)
    report['var_parametric'] = var_param

    # 4. CVaR
    cvar_result = calc_cvar(prices, confidence=0.95)
    report['cvar_95'] = cvar_result

    # 5. 最大回撤
    dd = calc_max_drawdown(prices)
    report['max_drawdown'] = dd

    # 6. 夏普比率
    sharpe = calc_sharpe_ratio(returns)
    report['sharpe'] = sharpe

    # 7. ATR止损
    atr = calc_atr_stop_loss(kline)
    report['atr_stop_loss'] = atr

    # 8. 凯利仓位 (基于回测交易统计)
    # 先尝试从现有回测数据获取
    kelly = _estimate_kelly_from_data(code, returns)
    report['kelly_position'] = kelly

    # 9. 波动率
    vol_daily = np.nanstd(returns)
    vol_annual = vol_daily * math.sqrt(252)
    report['volatility'] = {
        'daily_pct': round(float(vol_daily * 100), 4),
        'annual_pct': round(float(vol_annual * 100), 2),
    }

    # 10. 最大单日涨幅/跌幅
    report['max_1d_gain_pct'] = round(float(np.max(returns) * 100), 2)
    report['max_1d_loss_pct'] = round(float(np.min(returns) * 100), 2)

    # 11. 风险评估等级
    report['risk_grade'] = _assess_risk_grade(report)

    # 12. 持仓关联分析
    if position and position.get('shares') and position.get('cost'):
        shares = position['shares']
        cost = position['cost']
        market_value = shares * current_price
        cost_basis = shares * cost
        pnl = market_value - cost_basis
        pnl_pct = (current_price / cost - 1) * 100

        # 基于VaR的最大可能损失
        var_pct_val = var_result.get('var_pct', 0) or 0
        max_loss_estimate = (var_pct_val / 100) * market_value if market_value > 0 else 0

        report['position_analysis'] = {
            'shares': shares,
            'cost_price': round(cost, 2),
            'current_price': round(float(current_price), 2),
            'market_value': round(market_value, 2),
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'var_95_max_loss': round(max_loss_estimate, 2),
            'var_95_max_loss_pct': round(var_result.get('var_pct', 0) or 0, 2),
        }

        # 建议止损
        if atr.get('stop_loss_price'):
            stop_price = atr['stop_loss_price']
            stop_loss = (cost - stop_price) * shares
            report['position_analysis']['suggested_stop_loss'] = round(stop_price, 2)
            report['position_analysis']['stop_loss_amount'] = round(stop_loss, 2)
            report['position_analysis']['stop_loss_pct'] = round((cost - stop_price) / cost * 100, 2)

        # 建议仓位调整
        if kelly.get('is_valid') and kelly.get('fractional_pct', 0) > 0:
            kelly_pct = kelly['fractional_pct'] / 100
            # 当前仓位占假设总资金的百分比 (假设总资金 = 持仓市值 / 建议仓位)
            report['position_analysis']['kelly_suggested_pct'] = kelly['fractional_pct']
            if kelly_pct > 0:
                implied_capital = market_value / kelly_pct
                report['position_analysis']['implied_total_capital'] = round(implied_capital, 2)

    return report


def _estimate_kelly_from_data(code: str, returns: np.ndarray) -> Dict:
    """基于历史交易数据估算凯利参数"""
    try:
        # 从历史收益率估算 win_rate, avg_win, avg_loss
        if len(returns) < 30:
            return {'is_valid': False, 'explanation': '历史数据不足'}

        wins = returns[returns > 0]
        losses = returns[returns < 0]

        if len(wins) == 0 or len(losses) == 0:
            return {'is_valid': False, 'explanation': '无盈利或亏损数据'}

        win_rate = float(len(wins) / (len(wins) + len(losses)))
        avg_win = float(np.mean(wins)) * 100
        avg_loss = abs(float(np.mean(losses))) * 100

        return calc_kelly_position(win_rate, avg_win, avg_loss, fractional=0.5)
    except Exception as e:
        return {'is_valid': False, 'explanation': str(e)}


def _assess_risk_grade(report: Dict) -> str:
    """综合评估风险等级"""
    score = 0

    # VaR维度
    var_pct = report.get('var_95', {}).get('var_pct')
    if var_pct is not None:
        if var_pct <= 2:
            score += 1  # 低风险
        elif var_pct >= 8:
            score -= 1  # 高风险

    # 回撤维度
    max_dd = report.get('max_drawdown', {}).get('max_drawdown_pct', 0)
    if max_dd <= 15:
        score += 1
    elif max_dd >= 40:
        score -= 1

    # 夏普维度
    sharpe = report.get('sharpe', {}).get('sharpe_ratio')
    if sharpe is not None:
        if sharpe >= 1.0:
            score += 1
        elif sharpe <= 0:
            score -= 1

    # 波动率维度
    vol = report.get('volatility', {}).get('annual_pct', 0)
    if vol <= 25:
        score += 1
    elif vol >= 60:
        score -= 1

    if score >= 3:
        return '低风险'
    elif score >= 1:
        return '中等风险'
    elif score >= -1:
        return '高风险'
    else:
        return '极高风险'


# ═══════════════════════════════════════════
# 组合层面风险分析
# ═══════════════════════════════════════════

def portfolio_risk_report(
    codes: list,
    weights: list = None,
    lookback_days: int = 120,
) -> dict:
    """
    组合风险报告 — 分析多只股票的组合风险特征

    Args:
        codes: 股票代码列表
        weights: 各股票权重（默认等权）
        lookback_days: 回看天数

    Returns:
        dict: {correlation, concentration, portfolio_var, diversification_score, ...}
    """
    import math

    n = len(codes)
    if n < 2:
        return {'error': '至少需要2只股票', 'code_count': n}

    if weights is None:
        weights = [1.0 / n] * n
    else:
        total_w = sum(weights)
        weights = [w / total_w for w in weights]

    # 1. 获取每只股票的日收益率
    all_returns = {}
    all_prices = {}
    names = {}
    for code in codes:
        try:
            kline = get_daily_kline(str(code), count=lookback_days + 30)
            if kline is not None and len(kline) >= 30:
                prices = kline['close'].values.astype(float)
                returns = np.diff(prices) / prices[:-1]
                returns = returns[~np.isnan(returns)]
                if len(returns) >= 20:
                    all_returns[code] = returns[-min(252, len(returns)):]
                    all_prices[code] = prices[-min(252, len(prices)):]
                    # 尝试获取名称
                    try:
                        from data_fetchers import get_realtime_data
                        rt = get_realtime_data(str(code))
                        if rt and isinstance(rt, dict):
                            names[code] = rt.get('name', code)
                        else:
                            names[code] = code
                    except Exception:
                        names[code] = code
        except Exception:
            continue

    valid_codes = list(all_returns.keys())
    if len(valid_codes) < 2:
        return {'error': '有效数据不足', 'valid_codes': valid_codes}

    # 2. 对齐数据长度
    min_len = min(len(all_returns[c]) for c in valid_codes)
    returns_matrix = np.column_stack([all_returns[c][-min_len:] for c in valid_codes])

    # 重新调整权重（只算有效股票）
    valid_weights = []
    valid_weights_map = {}
    for i, code in enumerate(codes):
        if code in valid_codes:
            valid_weights_map[code] = weights[i]
    w_sum = sum(valid_weights_map.values())
    for code in valid_codes:
        valid_weights.append(valid_weights_map[code] / w_sum)

    w = np.array(valid_weights)

    # 3. 相关性矩阵
    corr_matrix = np.corrcoef(returns_matrix.T)
    corr_pairs = []
    for i in range(len(valid_codes)):
        for j in range(i + 1, len(valid_codes)):
            corr_pairs.append({
                'pair': f"{names.get(valid_codes[i], valid_codes[i])} ↔ {names.get(valid_codes[j], valid_codes[j])}",
                'correlation': round(float(corr_matrix[i, j]), 3),
                'level': '高相关' if abs(corr_matrix[i, j]) > 0.7 else (
                    '中等相关' if abs(corr_matrix[i, j]) > 0.3 else '低相关'
                ),
            })

    avg_correlation = round(float(np.mean(np.abs(corr_matrix - np.eye(len(valid_codes))))), 3)

    # 4. 组合收益率和波动率
    portfolio_returns = returns_matrix @ w
    portfolio_vol_daily = float(np.nanstd(portfolio_returns))
    portfolio_vol_annual = portfolio_vol_daily * math.sqrt(252)
    portfolio_return_annual = float(np.nanmean(portfolio_returns)) * 252

    # 5. 组合 VaR / CVaR
    portfolio_var_95 = float(np.percentile(portfolio_returns, 5))
    tail_returns = portfolio_returns[portfolio_returns <= portfolio_var_95]
    portfolio_cvar_95 = float(np.mean(tail_returns)) if len(tail_returns) > 0 else portfolio_var_95
    portfolio_max_dd = calc_max_drawdown(np.cumprod(1 + portfolio_returns))

    # 6. 行业集中度
    sector_concentration = _calc_sector_concentration(valid_codes, w)

    # 7. 分散化评分 (0-100)
    divers_score = _calc_diversification_score(
        avg_correlation, len(valid_codes), sector_concentration.get('hhi', 1.0)
    )

    # 8. 个股风险贡献
    individual_var_contributions = []
    for i, code in enumerate(valid_codes):
        single_var = calc_var_historical(all_prices[code], confidence=0.95)
        individual_var_contributions.append({
            'code': code,
            'name': names.get(code, code),
            'weight_pct': round(float(w[i]) * 100, 1),
            'var_95_pct': single_var.get('var_pct'),
            'risk_contribution': round(float(w[i]) * float(single_var.get('var_pct', 0) or 0), 2),
        })

    return {
        'code_count': len(valid_codes),
        'codes': [{'code': c, 'name': names.get(c, c)} for c in valid_codes],
        'weights': {c: round(float(w[i]) * 100, 1) for i, c in enumerate(valid_codes)},
        'correlation': {
            'avg_absolute_correlation': avg_correlation,
            'pairs': corr_pairs,
            'interpretation': '高相关性' if avg_correlation > 0.6 else (
                '中等相关性' if avg_correlation > 0.3 else '低相关性（分散化好）'
            ),
        },
        'portfolio_stats': {
            'annual_return_pct': round(portfolio_return_annual * 100, 2),
            'annual_volatility_pct': round(portfolio_vol_annual * 100, 2),
            'sharpe_ratio': round(
                (portfolio_return_annual - 0.02) / portfolio_vol_annual, 4
            ) if portfolio_vol_annual > 0 else 0,
            'var_95_pct': round(abs(portfolio_var_95) * 100, 2),
            'cvar_95_pct': round(abs(portfolio_cvar_95) * 100, 2),
            'max_drawdown_pct': portfolio_max_dd.get('max_drawdown_pct', 0),
        },
        'sector_concentration': sector_concentration,
        'diversification_score': divers_score,
        'individual_risks': individual_var_contributions,
        'generated_at': datetime.now().isoformat(),
    }


def _calc_sector_concentration(codes: list, weights: np.ndarray) -> dict:
    """计算行业集中度"""
    try:
        from models import SessionLocal
        from db import get_latest_financial

        db = SessionLocal()
        sector_map = {}
        try:
            from sector_data import get_sector_stocks, get_all_sectors_with_stocks
            all_sectors = get_all_sectors_with_stocks()
            for code in codes:
                for sector_name, stock_list in all_sectors.items():
                    if code in stock_list:
                        if code not in sector_map:
                            sector_map[code] = []
                        sector_map[code].append(sector_name)
        except Exception:
            pass
        finally:
            db.close()

        # 计算各行业权重
        sector_weights = {}
        for i, code in enumerate(codes):
            sectors = sector_map.get(code, ['未分类'])
            for sector in sectors:
                sector_weights[sector] = sector_weights.get(sector, 0) + float(weights[i])

        # HHI 指数
        hhi = sum((w / 100) ** 2 for w in sector_weights.values()) if sector_weights else 1.0

        top_sector = max(sector_weights, key=sector_weights.get) if sector_weights else '未知'
        top_pct = sector_weights.get(top_sector, 0) if sector_weights else 0

        level = '高度集中' if hhi > 0.5 else ('适度集中' if hhi > 0.2 else '分散')

        return {
            'sectors': sector_weights,
            'hhi': round(hhi, 4),
            'top_sector': top_sector,
            'top_sector_pct': round(top_pct, 1),
            'level': level,
        }
    except Exception as e:
        return {'error': str(e), 'hhi': 1.0}


def _calc_diversification_score(avg_corr: float, num_stocks: int, sector_hhi: float) -> int:
    """
    分散化评分 0-100
    - 低相关性 → 高分
    - 多股票 → 高分 (边际递减)
    - 行业分散 → 高分
    """
    score = 50
    # 相关性得分
    score += (1 - avg_corr) * 30
    # 股票数量得分
    score += min(num_stocks * 5, 15)
    # 行业分散得分
    score += (1 - sector_hhi) * 15
    return max(0, min(100, int(score)))


def portfolio_risk_text(codes: list, weights: list = None) -> str:
    """生成组合风险文本摘要（用于AI prompt注入）"""
    report = portfolio_risk_report(codes, weights)
    if 'error' in report:
        return f"[组合风险] {report['error']}"

    lines = [
        f"## 组合风险摘要 ({len(report['codes'])}只股票)",
        f"- 分散化评分: {report['diversification_score']}/100",
        f"- 平均相关性: {report['correlation']['avg_absolute_correlation']}",
        f"- 行业集中度: {report['sector_concentration'].get('level', '未知')}",
        f"- 年化波动率: {report['portfolio_stats']['annual_volatility_pct']}%",
        f"- VaR(95%): {report['portfolio_stats']['var_95_pct']}%",
        f"- 最大回撤: {report['portfolio_stats']['max_drawdown_pct']}%",
        f"- 夏普比率: {report['portfolio_stats']['sharpe_ratio']}",
    ]
    return '\n'.join(lines)# ═══════════════════════════════════════════════════════════════
# 便捷函数: 快速获取股票风险摘要
# ═══════════════════════════════════════════════════════════════

def quick_risk_summary(code: str, position: Optional[Dict] = None) -> str:
    """
    生成文本格式的风险摘要 (用于注入AI prompt或快速查看)
    """
    report = risk_report(code, position)

    if report.get('risk_grade') in ('data_insufficient', 'data_error'):
        return f"[{code}] 风险数据不可用"

    lines = [
        f"## {code} 风险摘要",
        f"- 风险等级: {report['risk_grade']}",
        f"- VaR(95%): {report.get('var_95', {}).get('var_pct', 'N/A')}%",
        f"- CVaR(95%): {report.get('cvar_95', {}).get('cvar_pct', 'N/A')}%",
        f"- 最大回撤: {report.get('max_drawdown', {}).get('max_drawdown_pct', 'N/A')}%",
        f"- 年化波动率: {report.get('volatility', {}).get('annual_pct', 'N/A')}%",
        f"- 夏普比率: {report.get('sharpe', {}).get('sharpe_ratio', 'N/A')}",
    ]

    kelly = report.get('kelly_position', {})
    if kelly.get('is_valid'):
        lines.append(f"- 建议仓位(半凯利): {kelly.get('fractional_pct', 'N/A')}% (风险等级: {kelly.get('risk_level', 'N/A')})")

    atr = report.get('atr_stop_loss', {})
    if atr.get('stop_loss_price'):
        lines.append(f"- ATR止损价: {atr['stop_loss_price']} ({atr.get('stop_loss_pct', 'N/A')}%)")

    pa = report.get('position_analysis')
    if pa:
        lines.append(f"- 持仓: {pa['shares']}股 成本{pa['cost_price']} 浮盈{pa['pnl_pct']}%")
        if pa.get('suggested_stop_loss'):
            lines.append(f"- 建议止损: {pa['suggested_stop_loss']} (亏{pa.get('stop_loss_amount', 'N/A')}元)")

    return '\n'.join(lines)


def _safe_bool(val):
    """Convert numpy.bool_ to Python bool for JSON serialization"""
    return bool(val) if val is not None else False


def _safe_float(val):
    """Convert numpy.float to Python float"""
    return float(val) if val is not None else None

# ═══════════════════════════════════════════════════════════════
#
# 核心理念：
#   1. 找到正期望值的交易 (Edge > 0)
#   2. 用凯利公式确定最优仓位 (Kelly Criterion)
#   3. 控制破产风险 (Risk of Ruin)
#   4. 动态调整：不确定性 → 降仓，回撤 → 降仓
#   5. 多层止损：硬止损 + 移动止损 + 时间止损
# ═══════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════
# 1. 风险破产概率 (Risk of Ruin)
# ═══════════════════════════════════════════════════════════════

def calc_risk_of_ruin(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    capital_units: float = 20.0,
    position_pct: float = None,
) -> Dict:
    """
    计算破产风险 — 「击败庄家」核心概念

    即使有正期望值，连续亏损也会导致破产。
    RoR = ((1 - edge) / (1 + edge)) ^ capital_units

    Args:
        win_rate: 胜率 (0-1)
        avg_win_pct: 平均盈利%
        avg_loss_pct: 平均亏损%
        capital_units: 资金单位数 = 总资金 / 单笔风险金额
        position_pct: 仓位百分比。如果提供，自动计算 capital_units

    Returns:
        dict: {risk_of_ruin_pct, capital_units, max_consecutive_losses,
               survival_horizon_trades, interpretation}
    """
    loss_rate = 1 - win_rate

    if avg_loss_pct <= 0:
        return {'risk_of_ruin_pct': None, 'error': 'avg_loss_pct 必须 > 0'}

    # 计算 edge (期望收益率)
    edge = (win_rate * avg_win_pct - loss_rate * avg_loss_pct) / 100

    # 如果提供仓位百分比，计算 capital_units
    if position_pct is not None and position_pct > 0:
        # capital_units = 单笔亏损能承受多少次
        # 每笔亏损 = position_pct% * avg_loss_pct%
        loss_per_trade_pct = (position_pct / 100) * avg_loss_pct
        if loss_per_trade_pct > 0:
            capital_units = 100 / loss_per_trade_pct
        else:
            capital_units = float('inf')

    if capital_units <= 0:
        return {'risk_of_ruin_pct': None, 'error': 'capital_units 必须 > 0'}

    # 经典破产公式 (Thorp)
    if edge <= 0:
        # 负期望值 → 必然破产
        risk_of_ruin = 1.0
        interpretation = '🔴 负期望值，长期必然亏损。不要交易。'
    elif edge >= 1.0:
        risk_of_ruin = 0.0
        interpretation = '🟢 极端正期望值，几乎不可能破产。'
    else:
        # RoR = ((1-edge)/(1+edge)) ^ capital_units
        ror_ratio = (1 - edge) / (1 + edge)
        if ror_ratio <= 0:
            risk_of_ruin = 0.0
        else:
            risk_of_ruin = ror_ratio ** capital_units

        if risk_of_ruin < 0.01:
            interpretation = '🟢 破产风险极低 (<1%)，仓位合理。'
        elif risk_of_ruin < 0.05:
            interpretation = '🟡 破产风险可控 (1-5%)，可继续当前仓位。'
        elif risk_of_ruin < 0.15:
            interpretation = '🟠 破产风险偏高 (5-15%)，建议降低仓位。'
        elif risk_of_ruin < 0.50:
            interpretation = '🔴 破产风险很高 (15-50%)，必须大幅降低仓位！'
        else:
            interpretation = '💀 破产风险极高 (>50%)，当前仓位必然导致爆仓！'

    # 最大连续亏损次数估计
    if loss_rate > 0 and loss_rate < 1:
        # 95%置信度下的最大连续亏损
        max_consecutive = math.ceil(math.log(0.05) / math.log(loss_rate)) if loss_rate > 0 else 0
    else:
        max_consecutive = 0

    # 生存期限 (在95%置信度下能交易多少次)
    if risk_of_ruin > 0 and risk_of_ruin < 1:
        # 简化的生存交易次数估计
        if edge > 0:
            half_life = math.log(0.5) / math.log(ror_ratio) if ror_ratio > 0 else float('inf')
            survival_trades = int(half_life * 3)  # 3个半衰期
        else:
            survival_trades = 0
    else:
        survival_trades = None

    return {
        'risk_of_ruin_pct': round(risk_of_ruin * 100, 2),
        'risk_of_ruin_decimal': round(risk_of_ruin, 6),
        'capital_units': round(capital_units, 1),
        'edge_pct': round(edge * 100, 2),
        'max_consecutive_losses_95pct': max_consecutive,
        'survival_horizon_trades': survival_trades,
        'interpretation': interpretation,
        'recommendation': _ror_recommendation(risk_of_ruin, edge, position_pct),
    }


def _ror_recommendation(ror: float, edge: float, position_pct: float = None) -> str:
    """基于破产风险给出仓位建议"""
    if edge <= 0:
        return '不交易：期望值为负。'
    if ror < 0.01:
        return '当前仓位安全，可维持。'
    if ror < 0.05:
        return '当前仓位可接受，但不要再增加。'
    if ror < 0.15:
        if position_pct:
            suggested = position_pct * 0.6
            return f'建议降至 {suggested:.1f}% 仓位以降低破产风险。'
        return '建议降低仓位至当前60%。'
    if ror < 0.50:
        if position_pct:
            suggested = position_pct * 0.4
            return f'必须降至 {suggested:.1f}% 仓位以下！'
        return '必须大幅降低仓位！'
    return '立即减仓至最低水平，当前仓位不可持续！'


# ═══════════════════════════════════════════════════════════════
# 2. 期望值/优势计算 (Expected Value & Edge)
# ═══════════════════════════════════════════════════════════════

def calc_trade_edge(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    entry_price: float = None,
    target_price: float = None,
    stop_price: float = None,
) -> Dict:
    """
    计算单笔交易的期望值和优势

    EV = p * win - (1-p) * loss
    Edge = EV / avg_loss  (标准化优势)

    支持两种模式:
    1. 统计模式: 给定历史 win_rate/avg_win/avg_loss
    2. 价位模式: 给定 entry/target/stop 自动计算盈亏比

    Args:
        win_rate: 胜率
        avg_win_pct: 平均盈利%
        avg_loss_pct: 平均亏损%
        entry_price: 入场价 (价位模式)
        target_price: 目标价 (价位模式)
        stop_price: 止损价 (价位模式)

    Returns:
        dict: {edge_pct, ev_pct, profit_factor, is_positive_edge, kelly_pct, ...}
    """
    # 价位模式
    if entry_price and target_price and stop_price:
        if entry_price <= 0 or target_price <= 0 or stop_price <= 0:
            return {'error': '价格必须 > 0'}
        # 做多
        avg_win_pct = abs(target_price - entry_price) / entry_price * 100
        avg_loss_pct = abs(entry_price - stop_price) / entry_price * 100
        profit_loss_ratio = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 0
    else:
        profit_loss_ratio = avg_win_pct / avg_loss_pct if avg_loss_pct > 0 else 0

    loss_rate = 1 - win_rate

    # 期望收益率 (每笔交易的期望收益%)
    ev_pct = (win_rate * avg_win_pct - loss_rate * avg_loss_pct)

    # 标准化优势 (edge)
    if avg_loss_pct > 0:
        edge = ev_pct / avg_loss_pct
    else:
        edge = ev_pct  # fallback

    # 利润因子
    total_win = win_rate * avg_win_pct
    total_loss = loss_rate * avg_loss_pct
    profit_factor = total_win / total_loss if total_loss > 0 else float('inf')

    # 凯利仓位
    if avg_loss_pct > 0:
        b = profit_loss_ratio
        kelly = (win_rate * b - loss_rate) / b
        kelly = max(0, min(kelly, 1.0))
    else:
        kelly = 0

    # 判断
    if ev_pct > 1.0:
        assessment = '🟢 强正期望值，积极交易'
    elif ev_pct > 0.3:
        assessment = '🟢 正期望值，可以交易'
    elif ev_pct > 0:
        assessment = '🟡 微弱正期望值，谨慎交易'
    elif ev_pct > -0.3:
        assessment = '🟠 略微负期望值，不建议交易'
    else:
        assessment = '🔴 显著负期望值，禁止交易'

    return {
        'edge_pct': round(edge * 100, 2),
        'ev_per_trade_pct': round(ev_pct, 2),
        'profit_factor': round(profit_factor, 2),
        'is_positive_edge': _safe_bool(ev_pct > 0),
        'assessment': assessment,
        'kelly_pct': round(kelly * 100, 1),
        'win_rate_pct': round(win_rate * 100, 1),
        'avg_win_pct': round(avg_win_pct, 2),
        'avg_loss_pct': round(avg_loss_pct, 2),
        'profit_loss_ratio': round(profit_loss_ratio, 2),
        'entry_price': entry_price,
        'target_price': target_price,
        'stop_price': stop_price,
    }


# ═══════════════════════════════════════════════════════════════
# 3. 动态凯利 — 不确定性 + 回撤双调整
# ═══════════════════════════════════════════════════════════════

def calc_dynamic_kelly(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    sample_size: int = 30,
    current_drawdown_pct: float = 0,
    confidence: float = 0.95,
) -> Dict:
    """
    动态凯利仓位 — 「击败庄家」实战精髓

    Thorp 本人只用半凯利甚至1/4凯利，因为：
    1. 胜率估计有误差 (样本不足)
    2. 市场条件变化
    3. 连续亏损后心理压力

    调整因子:
    - 样本不足 → 降仓 (小样本胜率不可靠)
    - 当前回撤 → 降仓 (回撤中降低风险暴露)

    Args:
        win_rate: 历史胜率
        avg_win_pct: 平均盈利%
        avg_loss_pct: 平均亏损%
        sample_size: 样本交易次数
        current_drawdown_pct: 当前回撤%
        confidence: 置信水平

    Returns:
        dict: {base_kelly, adjusted_kelly, adjustments, ...}
    """
    loss_rate = 1 - win_rate

    if avg_loss_pct <= 0:
        return {'adjusted_kelly_pct': 0, 'error': 'avg_loss_pct 必须 > 0'}

    # 基础凯利
    b = avg_win_pct / avg_loss_pct
    base_kelly = (win_rate * b - loss_rate) / b
    base_kelly = max(0, min(base_kelly, 1.0))

    adjustments = []
    multiplier = 1.0

    # 调整1: 样本不足折扣
    if sample_size < 100:
        # 胜率的标准误差 ≈ sqrt(p*(1-p)/n)
        se = math.sqrt(win_rate * (1 - win_rate) / max(sample_size, 1))
        # 95%置信下界
        z_score = 1.645  # 单尾95%
        win_rate_lower = win_rate - z_score * se
        win_rate_lower = max(0.01, win_rate_lower)  # 不低于1%

        # 用下界胜率重算凯利
        b_lower = avg_win_pct / avg_loss_pct
        kelly_lower = (win_rate_lower * b_lower - (1 - win_rate_lower)) / b_lower
        kelly_lower = max(0, min(kelly_lower, 1.0))

        confidence_discount = kelly_lower / base_kelly if base_kelly > 0 else 0
        # 样本折扣不低于0.3 (即最多折70%，避免小样本时完全归零)
        confidence_discount = max(confidence_discount, 0.3)
        multiplier *= confidence_discount
        adjustments.append({
            'type': 'sample_size',
            'sample_size': sample_size,
            'win_rate_lower_bound': round(win_rate_lower * 100, 1),
            'confidence_discount': round(confidence_discount, 3),
            'reason': f'仅{sample_size}笔交易，胜率估计不确定',
        })

    # 调整2: 当前回撤折扣
    if current_drawdown_pct > 5:
        # 回撤越大，折扣越大
        dd_discount = max(0.3, 1.0 - (current_drawdown_pct - 5) / 50)
        multiplier *= dd_discount
        adjustments.append({
            'type': 'drawdown',
            'current_drawdown_pct': round(current_drawdown_pct, 1),
            'drawdown_discount': round(dd_discount, 3),
            'reason': f'当前回撤{current_drawdown_pct:.1f}%，降低风险暴露',
        })

    # 调整3: 默认保守系数 (Thorp 本人用半凯利)
    conservatism = 0.5  # 半凯利
    multiplier *= conservatism
    adjustments.append({
        'type': 'conservatism',
        'factor': conservatism,
        'reason': 'Thorp半凯利原则：永远不押满凯利',
    })

    adjusted_kelly = base_kelly * multiplier

    # 风险等级
    if adjusted_kelly >= 0.20:
        risk_level = '激进'
    elif adjusted_kelly >= 0.10:
        risk_level = '适中'
    elif adjusted_kelly >= 0.03:
        risk_level = '保守'
    else:
        risk_level = '极保守'

    return {
        'base_kelly_pct': round(base_kelly * 100, 1),
        'adjusted_kelly_pct': round(adjusted_kelly * 100, 1),
        'total_multiplier': round(multiplier, 3),
        'risk_level': risk_level,
        'adjustments': adjustments,
        'win_rate': round(win_rate * 100, 1),
        'avg_win_pct': round(avg_win_pct, 2),
        'avg_loss_pct': round(avg_loss_pct, 2),
        'sample_size': sample_size,
    }


# ═══════════════════════════════════════════════════════════════
# 4. 多层止损体系
# ═══════════════════════════════════════════════════════════════

def calc_multi_tier_stop(
    code: str,
    entry_price: float,
    max_loss_pct: float = 8.0,
    atr_multiplier: float = 2.0,
    trailing_pct: float = 5.0,
    time_limit_days: int = 20,
) -> Dict:
    """
    多层止损体系 — 从「击败庄家」延伸的实战风控

    三层止损：
    1. 硬止损 (Hard Stop): 基于最大可接受亏损
    2. 移动止损 (Trailing Stop): 盈利后保护利润
    3. 时间止损 (Time Stop): 超时未达预期则退出

    Args:
        code: 股票代码
        entry_price: 入场价格
        max_loss_pct: 最大可接受亏损% (硬止损)
        atr_multiplier: ATR倍数 (波动止损)
        trailing_pct: 移动止损回撤%
        time_limit_days: 时间止损天数

    Returns:
        dict: {hard_stop, trailing_stop, atr_stop, time_stop, summary}
    """
    stops = {
        'entry_price': entry_price,
        'generated_at': datetime.now().isoformat(),
    }

    try:
        kline = get_daily_kline(code, count=120)
        if kline is None or len(kline) < 15:
            stops['error'] = 'K线数据不足'
            return stops

        closes = kline['close'].values.astype(float)
        current_price = closes[-1]

        # 1. 硬止损
        hard_stop = entry_price * (1 - max_loss_pct / 100)
        hard_loss_pct = (entry_price - hard_stop) / entry_price * 100

        stops['hard_stop'] = {
            'price': round(hard_stop, 2),
            'loss_pct': round(hard_loss_pct, 2),
            'loss_per_share': round(entry_price - hard_stop, 2),
            'type': 'hard',
        }

        # 2. ATR波动止损
        atr_result = calc_atr_stop_loss(kline, multiplier=atr_multiplier)
        if atr_result.get('stop_loss_price'):
            atr_value = atr_result['atr_value']
            atr_stop = entry_price - atr_multiplier * atr_value
            # 不能高于硬止损
            atr_stop = max(atr_stop, hard_stop)

            stops['atr_stop'] = {
                'price': round(atr_stop, 2),
                'atr_value': round(atr_value, 2),
                'atr_multiplier': atr_multiplier,
                'loss_pct': round((entry_price - atr_stop) / entry_price * 100, 2),
                'type': 'volatility',
            }

        # 3. 移动止损 (基于近期高点)
        recent_high = max(closes[-20:]) if len(closes) >= 20 else closes[-1]
        trailing_stop = recent_high * (1 - trailing_pct / 100)
        # 不能低于硬止损
        trailing_stop = max(trailing_stop, hard_stop)

        stops['trailing_stop'] = {
            'price': round(trailing_stop, 2),
            'recent_high': round(recent_high, 2),
            'trailing_pct': trailing_pct,
            'loss_pct': round((entry_price - trailing_stop) / entry_price * 100, 2),
            'type': 'trailing',
            'note': f'从近期高点{recent_high:.2f}回撤{trailing_pct}%',
        }

        # 4. 时间止损
        stops['time_stop'] = {
            'entry_date': datetime.now().strftime('%Y-%m-%d'),
            'deadline_date': (datetime.now() + timedelta(days=time_limit_days)).strftime('%Y-%m-%d'),
            'max_hold_days': time_limit_days,
            'condition': f'超过{time_limit_days}个交易日未触发止盈或未盈利，强制退出',
            'type': 'time',
        }

        # 5. 综合建议
        all_stops = [hard_stop]
        if atr_result.get('stop_loss_price'):
            all_stops.append(atr_stop)
        effective_stop = max(all_stops)  # 最高 = 最紧

        stops['summary'] = {
            'effective_stop_price': round(effective_stop, 2),
            'effective_stop_pct': round((entry_price - effective_stop) / entry_price * 100, 2),
            'current_price': round(float(current_price), 2),
            'current_pnl_pct': round((current_price / entry_price - 1) * 100, 2),
            'stop_triggered': bool(current_price <= effective_stop),
            'strategy': '取硬止损/ATR止损中较紧者作为有效止损',
        }

        return stops

    except Exception as e:
        stops['error'] = str(e)
        return stops


# ═══════════════════════════════════════════════════════════════
# 5. 回撤感知仓位调整
# ═══════════════════════════════════════════════════════════════

def calc_drawdown_aware_position(
    total_capital: float,
    base_position_pct: float,
    current_drawdown_pct: float,
    max_position_pct: float = 30.0,
    min_position_pct: float = 5.0,
) -> Dict:
    """
    回撤感知仓位 — 「击败庄家」资金管理实践

    当账户出现回撤时自动降低仓位，保护资金。
    当恢复盈利时逐步恢复仓位。

    规则 (Thorp风格):
    - 回撤 < 5%:  维持基础仓位
    - 回撤 5-15%: 降至基础仓位 × 0.7
    - 回撤 15-30%: 降至基础仓位 × 0.4
    - 回撤 > 30%:  降至最低仓位，专注恢复

    Args:
        total_capital: 总资金
        base_position_pct: 基础仓位%
        current_drawdown_pct: 当前回撤%
        max_position_pct: 最大仓位上限%
        min_position_pct: 最小仓位%

    Returns:
        dict: {adjusted_pct, adjusted_amount, discount, drawdown_level, ...}
    """
    base_pct = min(base_position_pct, max_position_pct)
    base_pct = max(base_pct, min_position_pct)

    # 回撤折扣表
    if current_drawdown_pct < 5:
        discount = 1.0
        level = 'normal'
    elif current_drawdown_pct < 10:
        discount = 0.85
        level = 'mild'
    elif current_drawdown_pct < 15:
        discount = 0.7
        level = 'moderate'
    elif current_drawdown_pct < 25:
        discount = 0.5
        level = 'significant'
    elif current_drawdown_pct < 35:
        discount = 0.35
        level = 'severe'
    else:
        discount = 0.2
        level = 'critical'

    adjusted_pct = base_pct * discount
    adjusted_pct = max(adjusted_pct, min_position_pct)
    adjusted_amount = total_capital * adjusted_pct / 100

    return {
        'total_capital': round(total_capital, 2),
        'base_position_pct': round(base_pct, 1),
        'adjusted_position_pct': round(adjusted_pct, 1),
        'adjusted_amount': round(adjusted_amount, 2),
        'discount_factor': round(discount, 2),
        'drawdown_level': level,
        'current_drawdown_pct': round(current_drawdown_pct, 1),
        'rule': f'回撤{level}级别 → 仓位系数 {discount:.0%}',
    }


# ═══════════════════════════════════════════════════════════════
# 6. 综合仓位+止损计算 (一站式)
# ═══════════════════════════════════════════════════════════════

def beat_the_dealer_full(
    code: str,
    total_capital: float,
    entry_price: float = None,
    target_price: float = None,
    current_drawdown_pct: float = 0,
    win_rate: float = None,
    avg_win_pct: float = None,
    avg_loss_pct: float = None,
    sample_size: int = 30,
    risk_profile: str = 'moderate',
) -> Dict:
    """
    「击败庄家」一站式仓位+止损计算

    完整流程:
    1. 从K线估算历史交易统计 (如果没有提供 win_rate 等)
    2. 计算期望值 (Edge)
    3. 动态凯利仓位
    4. 风险破产概率
    5. 回撤感知调整
    6. 多层止损

    Args:
        code: 股票代码
        total_capital: 总资金
        entry_price: 计划入场价 (默认用当前价)
        target_price: 目标价
        current_drawdown_pct: 账户当前回撤%
        win_rate/avg_win/avg_loss: 手动提供交易统计
        sample_size: 样本数 (用于不确定性调整)
        risk_profile: 'conservative' | 'moderate' | 'aggressive'

    Returns:
        dict: 完整仓位+止损方案
    """
    result = {
        'code': code,
        'total_capital': round(total_capital, 2),
        'risk_profile': risk_profile,
        'generated_at': datetime.now().isoformat(),
    }

    try:
        # 获取行情数据
        kline = get_daily_kline(code, count=120)
        if kline is None or len(kline) < 30:
            result['error'] = 'K线数据不足'
            return result

        closes = kline['close'].values.astype(float)
        current_price = closes[-1]

        if entry_price is None:
            entry_price = current_price

        result['current_price'] = round(float(current_price), 2)
        result['entry_price'] = round(entry_price, 2)

        # Step 1: 估算交易统计 (如果没有手动提供)
        if win_rate is None or avg_win_pct is None or avg_loss_pct is None:
            returns = np.diff(closes) / closes[:-1]
            returns = returns[~np.isnan(returns)]

            if len(returns) >= 30:
                wins = returns[returns > 0]
                losses = returns[returns < 0]

                if len(wins) > 0 and len(losses) > 0:
                    est_win_rate = float(len(wins) / (len(wins) + len(losses)))
                    est_avg_win = float(np.mean(wins)) * 100
                    est_avg_loss = abs(float(np.mean(losses))) * 100

                    if win_rate is None:
                        win_rate = est_win_rate
                    if avg_win_pct is None:
                        avg_win_pct = est_avg_win
                    if avg_loss_pct is None:
                        avg_loss_pct = est_avg_loss

                    result['estimated_from'] = {
                        'method': 'daily_returns',
                        'sample_days': len(returns),
                    }
                else:
                    result['error'] = '无法从历史数据估算交易统计'
                    return result
            else:
                result['error'] = '历史数据不足'
                return result

        result['trade_stats'] = {
            'win_rate_pct': round(win_rate * 100, 1),
            'avg_win_pct': round(avg_win_pct, 2),
            'avg_loss_pct': round(avg_loss_pct, 2),
            'sample_size': sample_size,
        }

        # Step 2: 期望值计算
        edge_result = calc_trade_edge(
            win_rate, avg_win_pct, avg_loss_pct,
            entry_price=entry_price,
            target_price=target_price,
            stop_price=None,
        )
        result['edge_analysis'] = edge_result

        # Step 3: 动态凯利
        kelly_result = calc_dynamic_kelly(
            win_rate, avg_win_pct, avg_loss_pct,
            sample_size=sample_size,
            current_drawdown_pct=current_drawdown_pct,
        )
        result['kelly_analysis'] = kelly_result

        # Step 4: 根据风险偏好选择仓位比例
        kelly_pct = kelly_result['adjusted_kelly_pct']
        if risk_profile == 'conservative':
            position_pct = kelly_pct * 0.5  # 1/4凯利
        elif risk_profile == 'aggressive':
            position_pct = kelly_pct * 2.0  # 接近全凯利
        else:  # moderate
            position_pct = kelly_pct  # 半凯利 (已在动态凯利中应用0.5)

        position_pct = min(position_pct, 30.0)  # 单只上限30%
        position_pct = max(position_pct, 3.0)   # 最低3%

        # Step 5: 回撤感知调整
        dd_result = calc_drawdown_aware_position(
            total_capital, position_pct, current_drawdown_pct,
        )
        result['drawdown_adjustment'] = dd_result
        final_position_pct = dd_result['adjusted_position_pct']
        final_position_amount = total_capital * final_position_pct / 100

        # Step 6: 风险破产概率
        ror_result = calc_risk_of_ruin(
            win_rate, avg_win_pct, avg_loss_pct,
            position_pct=final_position_pct,
        )
        result['risk_of_ruin'] = ror_result

        # Step 7: 多层止损
        stop_result = calc_multi_tier_stop(
            code, entry_price,
            max_loss_pct=min(avg_loss_pct * 1.5, 10.0),
        )
        result['stop_loss_plan'] = stop_result

        # Step 8: 最终建议
        shares = int(final_position_amount / entry_price / 100) * 100  # 整手
        if shares < 100:
            shares = 0

        actual_amount = shares * entry_price
        actual_pct = actual_amount / total_capital * 100 if total_capital > 0 else 0

        result['final_recommendation'] = {
            'position_pct': round(final_position_pct, 1),
            'position_amount': round(final_position_amount, 2),
            'suggested_shares': shares,
            'actual_amount': round(actual_amount, 2),
            'actual_pct': round(actual_pct, 1),
            'remaining_capital': round(total_capital - actual_amount, 2),
        }

        # 风险总结
        if not edge_result.get('is_positive_edge'):
            result['verdict'] = '🔴 不交易: 期望值为负'
        elif ror_result.get('risk_of_ruin_pct', 100) > 15:
            result['verdict'] = '🟠 期望值为正但破产风险偏高，建议降仓'
        elif shares == 0:
            result['verdict'] = '🟡 资金不足以买入1手(100股)'
        else:
            result['verdict'] = f'🟢 可交易: {shares}股, 仓位{actual_pct:.1f}%, 有效止损{stop_result.get("summary", {}).get("effective_stop_price", "N/A")}'

        return result

    except Exception as e:
        result['error'] = f'{type(e).__name__}: {e}'
        return result
