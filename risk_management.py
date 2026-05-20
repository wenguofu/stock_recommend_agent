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


# ═══════════════════════════════════════════════════════════════
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
