#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""因子引擎 — 20因子量化评分系统 v2

因子分类:
  动量类: momentum_20d, momentum_60d, momentum_stability
  技术类: rsi_14, volume_ratio, ma_status, macd_signal, ma_distance, bollinger_pos
  资金类: money_flow_5d, turnover_rate, relative_strength
  价值类: pe_percentile, pb_ratio, earnings_yield
  质量类: roe, gross_margin, profit_yoy, debt_ratio
  风险类: volatility_20d, beta_60d

更新: 2026-05-20 — 从8因子扩展到20因子"""

import traceback
import time
import logging
logger = logging.getLogger(__name__)
from datetime import datetime

import numpy as np
import pandas as pd

from data_fetchers import (
    get_daily_kline, get_money_flow, get_money_flow_history,
    get_realtime_data, get_fundamental_data
)
from technical_indicators import (
    calculate_ma, calculate_macd, calculate_rsi
)
from utils import is_us_stock

# 因子默认权重 (v2: 20因子, 6大类)
DEFAULT_WEIGHTS = {
    # 动量类 (25%)
    'momentum_20d': 0.10,
    'momentum_60d': 0.08,
    'momentum_stability': 0.07,
    # 技术类 (25%)
    'rsi_14': 0.05,
    'volume_ratio': 0.04,
    'ma_status': 0.06,
    'macd_signal': 0.05,
    'ma_distance': 0.03,
    'bollinger_pos': 0.02,
    # 资金类 (15%)
    'money_flow_5d': 0.07,
    'turnover_rate': 0.04,
    'relative_strength': 0.04,
    # 价值类 (15%)
    'pe_percentile': 0.05,
    'pb_ratio': 0.03,
    'earnings_yield': 0.07,
    # 质量类 (15%)
    'roe': 0.06,
    'gross_margin': 0.04,
    'profit_yoy': 0.03,
    'debt_ratio': 0.02,
    # 风险类 (5%)
    'volatility_20d': 0.03,
    'beta_60d': 0.02,
}


def calculate_factors(code: str) -> dict:
    """计算8个量化因子

    Args:
        code: A股股票代码 (如 '300433')

    Returns:
        dict: {
            'success': bool,
            'factors': {momentum_20d, rsi_14, volume_ratio, ma_status,
                        macd_signal, money_flow_5d, pe_percentile, roe},
            'raw': {...}  # 原始计算数据
        }
    """
    result = {
        'success': False,
        'code': code,
        'timestamp': datetime.now().isoformat(),
        'factors': {},
        'raw': {},
        'error': None,
    }

    try:
        # 跳过美股
        if is_us_stock(code):
            result['error'] = '美股暂不支持因子分析'
            return result

        # 1. 获取日K线数据 (240天)
        logger.debug(f"[Factor] 获取 {code} 日K线...")
        daily_df = get_daily_kline(code, count=240)
        if daily_df is None or daily_df.empty or len(daily_df) < 30:
            result['error'] = f'K线数据不足 (需要>=30天, 实际{len(daily_df) if daily_df is not None else 0}天)'
            return result

        # 计算技术指标
        daily_df = calculate_ma(daily_df, periods=[5, 10, 20, 30, 60])
        daily_df = calculate_macd(daily_df)
        daily_df = calculate_rsi(daily_df, period=14)

        close = daily_df['close'].values
        volume = daily_df['volume'].values
        ma5 = daily_df['MA5'].values
        ma10 = daily_df['MA10'].values
        ma20 = daily_df['MA20'].values
        ma30 = daily_df['MA30'].values
        ma60 = daily_df['MA60'].values
        dif = daily_df['MACD_DIF'].values
        dea = daily_df['MACD_DEA'].values
        rsi14 = daily_df['RSI14'].values

        last_idx = len(daily_df) - 1

        # ---- momentum_20d: 20日动量 ----
        if len(close) >= 21:
            momentum_20d = (close[last_idx] / close[last_idx - 20] - 1) * 100
        else:
            momentum_20d = 0.0

        # ---- rsi_14 ----
        rsi_14 = float(rsi14[last_idx]) if not np.isnan(rsi14[last_idx]) else 50.0

        # ---- volume_ratio: 今日量/20日均量 ----
        if len(volume) >= 20:
            avg_vol_20 = np.mean(volume[-21:-1])
            if avg_vol_20 > 0:
                volume_ratio = volume[last_idx] / avg_vol_20
            else:
                volume_ratio = 1.0
        else:
            volume_ratio = 1.0

        # ---- ma_status: 均线排列 ----
        if not np.isnan(ma5[last_idx]) and not np.isnan(ma10[last_idx]) \
           and not np.isnan(ma20[last_idx]) and not np.isnan(ma30[last_idx]):
            v5, v10, v20, v30 = ma5[last_idx], ma10[last_idx], ma20[last_idx], ma30[last_idx]
            if v5 > v10 > v20 > v30:
                ma_status = 1   # 多头排列
            elif v5 < v10 < v20 < v30:
                ma_status = 0   # 空头排列
            else:
                ma_status = -1  # 混乱
        else:
            ma_status = -1

        # ---- macd_signal: MACD信号 ----
        if len(dif) >= 29 and not np.isnan(dif[last_idx]) and not np.isnan(dea[last_idx]):
            if dif[last_idx - 1] <= dea[last_idx - 1] and dif[last_idx] > dea[last_idx]:
                macd_signal = 1   # 金叉
            elif dif[last_idx - 1] >= dea[last_idx - 1] and dif[last_idx] < dea[last_idx]:
                macd_signal = -1  # 死叉
            else:
                macd_signal = 0   # 中性
        else:
            macd_signal = 0

        # ---- money_flow_5d: 5日资金流强度 ----
        time.sleep(0.1)
        money_flow_5d = _calc_money_flow_strength(code, close[last_idx])

        # ---- pe_percentile & roe: 复用 fundamental_data ----
        time.sleep(0.1)
        pe_percentile, roe = _calc_fundamental_factors(code)

        # ═══ v2 新增因子计算 ═══
        # 动量扩展
        momentum_extras = _calc_momentum_extras(daily_df)

        # 技术扩展
        tech_extras = _calc_technical_extras(daily_df)

        # 价值因子
        value_factors = _calc_value_factors(code)

        # 质量因子
        quality_factors = _calc_quality_factors(code)

        # 风险因子 (传入沪深300基准数据计算Beta)
        benchmark_returns = None
        try:
            benchmark_df = get_daily_kline('000300', count=120)
            if benchmark_df is not None and len(benchmark_df) >= 60:
                bm_close = benchmark_df['close'].values.astype(float)
                benchmark_returns = np.diff(bm_close) / bm_close[:-1]
        except Exception:
            pass
        risk_factors = _calc_risk_factors(daily_df, benchmark_returns)

        # 换手率
        turnover = _calc_turnover_factor(daily_df)

        # 相对强度
        rel_strength = _calc_relative_strength(code, daily_df)

        factors = {
            # 动量类
            'momentum_20d': round(momentum_20d, 2),
            'momentum_60d': round(momentum_extras['momentum_60d'], 2) if momentum_extras.get('momentum_60d') is not None else None,
            'momentum_stability': momentum_extras.get('momentum_stability'),
            # 技术类
            'rsi_14': round(rsi_14, 2),
            'volume_ratio': round(volume_ratio, 2),
            'ma_status': ma_status,
            'macd_signal': macd_signal,
            'ma_distance': tech_extras.get('ma_distance'),
            'bollinger_pos': tech_extras.get('bollinger_pos'),
            # 资金类
            'money_flow_5d': round(money_flow_5d, 2),
            'turnover_rate': round(turnover, 2) if turnover else None,
            'relative_strength': rel_strength,
            # 价值类
            'pe_percentile': round(pe_percentile, 2) if pe_percentile is not None else None,
            'pb_ratio': value_factors.get('pb_ratio'),
            'earnings_yield': value_factors.get('earnings_yield'),
            # 质量类
            'roe': round(roe, 2) if roe is not None else None,
            'gross_margin': quality_factors.get('gross_margin'),
            'profit_yoy': quality_factors.get('profit_yoy'),
            'debt_ratio': quality_factors.get('debt_ratio'),
            # 风险类
            'volatility_20d': risk_factors.get('volatility_20d'),
            'beta_60d': risk_factors.get('beta_60d'),
        }

        result['success'] = True
        result['factors'] = factors
        result['raw'] = {
            'close': float(close[last_idx]),
            'ma5': float(ma5[last_idx]) if not np.isnan(ma5[last_idx]) else None,
            'ma20': float(ma20[last_idx]) if not np.isnan(ma20[last_idx]) else None,
            'data_days': len(daily_df),
        }

    except Exception as e:
        result['error'] = str(e)
        traceback.print_exc()

    return result


def _calc_money_flow_strength(code: str, current_price: float) -> float:
    """计算5日资金流强度

    主力净流入 / (流通市值) * 100, 量化为 -5 到 +5 的分值
    """
    try:
        flow_history = get_money_flow_history(code, days=5)
        if not flow_history or not isinstance(flow_history, list) or len(flow_history) == 0:
            return 0.0

        # 近5日主力净流入累计 (万元)
        total_main_inflow = 0.0
        valid_days = 0
        for item in flow_history[:5]:
            main_in = item.get('main_net_inflow')
            if main_in is not None:
                try:
                    total_main_inflow += float(main_in)
                    valid_days += 1
                except (ValueError, TypeError):
                    pass

        if valid_days == 0:
            return 0.0

        # 估算流通市值 (万股 * 当前价格 / 10000 = 亿元)
        fundamental = get_fundamental_data(code)
        if fundamental and fundamental.get('circulating_shares'):
            circulating_shares = fundamental['circulating_shares']
            market_value = circulating_shares * 10000 * current_price / 10000  # 亿元
            if market_value > 0:
                # 主力净流入占流通市值比例, 缩放至-5~+5区间
                ratio = (total_main_inflow / 10000) / market_value  # 转为亿元
                strength = min(5.0, max(-5.0, ratio * 100))
                return strength

        return 0.0

    except Exception as e:
        logger.warning(f"[Factor] money_flow calc failed: {e}")
        return 0.0


def _calc_fundamental_factors(code: str):
    """计算PE分位和ROE因子

    Returns:
        (pe_percentile, roe) 元组
    """
    try:
        fundamental = get_fundamental_data(code)
        if not fundamental:
            return None, None

        roe = fundamental.get('roe')
        pe_ttm = fundamental.get('pe_ttm')

        # PE分位估算: 基于当前PE粗略判断
        # 使用行业PE作为参照
        pe_industry = fundamental.get('pe_industry')
        if pe_ttm is not None and pe_industry is not None and pe_industry > 0:
            # PE相对于行业PE的比值, 映射到0-100分位
            ratio = pe_ttm / pe_industry
            if ratio <= 0.5:
                pe_percentile = 90.0  # 很便宜
            elif ratio <= 0.8:
                pe_percentile = 70.0
            elif ratio <= 1.0:
                pe_percentile = 50.0
            elif ratio <= 1.3:
                pe_percentile = 30.0
            elif ratio <= 1.8:
                pe_percentile = 15.0
            else:
                pe_percentile = 5.0   # 很贵
        elif pe_ttm is not None:
            # 无行业参照, 使用绝对值
            if pe_ttm <= 0:
                pe_percentile = 50.0
            elif pe_ttm <= 15:
                pe_percentile = 80.0
            elif pe_ttm <= 25:
                pe_percentile = 60.0
            elif pe_ttm <= 40:
                pe_percentile = 40.0
            elif pe_ttm <= 60:
                pe_percentile = 20.0
            else:
                pe_percentile = 5.0
        else:
            pe_percentile = None

        return pe_percentile, roe

    except Exception as e:
        logger.warning(f"[Factor] fundamental calc failed: {e}")
        return None, None


# ═══════════════════════════════════════════════════════════════
# v2 新增因子计算函数
# ═══════════════════════════════════════════════════════════════

def _calc_momentum_extras(daily_df):
    """计算扩展动量因子: 60日动量, 动量稳定性"""
    close = daily_df['close'].values
    last_idx = len(daily_df) - 1

    # momentum_60d
    if len(close) >= 61:
        m60 = (close[last_idx] / close[last_idx - 60] - 1) * 100
    else:
        m60 = None

    # momentum_stability: 20日动量除以其标准差
    if len(close) >= 41:
        m20_series = []
        for i in range(20, len(close)):
            m20_series.append((close[i] / close[i - 20] - 1) * 100)
        if len(m20_series) >= 10:
            m20_mean = float(np.mean(m20_series))
            m20_std = float(np.std(m20_series))
            stability = m20_mean / m20_std if m20_std > 0 else 0
        else:
            stability = 0
    else:
        stability = 0

    return {'momentum_60d': m60, 'momentum_stability': round(stability, 4)}


def _calc_technical_extras(daily_df):
    """计算扩展技术因子: MA偏离, 布林带位置"""
    close = daily_df['close'].values
    last_idx = len(daily_df) - 1
    ma20 = daily_df['MA20'].values

    # ma_distance: 价格距MA20的偏离百分比
    if not np.isnan(ma20[last_idx]) and ma20[last_idx] > 0:
        ma_dist = (close[last_idx] / ma20[last_idx] - 1) * 100
    else:
        ma_dist = 0

    # bollinger_pos: 布林带位置 (0=下轨, 50=中轨, 100=上轨)
    if len(close) >= 20:
        ma = np.mean(close[-20:])
        std = np.std(close[-20:])
        if std > 0:
            upper = ma + 2 * std
            lower = ma - 2 * std
            boll_pos = (close[last_idx] - lower) / (upper - lower) * 100
            boll_pos = max(0, min(100, boll_pos))
        else:
            boll_pos = 50
    else:
        boll_pos = 50

    return {'ma_distance': round(float(ma_dist), 2), 'bollinger_pos': round(float(boll_pos), 2)}


def _calc_value_factors(code):
    """计算价值因子: PB, 盈利收益率"""
    try:
        from data_fetchers import get_fundamental_data
        fundamental = get_fundamental_data(code)

        pb_ratio = fundamental.get('pb') if fundamental else None
        pe_ttm = fundamental.get('pe_ttm') if fundamental else None

        # earnings_yield = 1/PE (盈利收益率)
        earnings_yield = None
        if pe_ttm is not None and pe_ttm > 0:
            earnings_yield = (1.0 / pe_ttm) * 100

        return {'pb_ratio': pb_ratio, 'earnings_yield': round(earnings_yield, 2) if earnings_yield else None}
    except Exception:
        return {'pb_ratio': None, 'earnings_yield': None}


def _calc_quality_factors(code):
    """计算质量因子: 毛利率, 利润增速, 负债率"""
    try:
        from data_fetchers import get_fundamental_data
        fundamental = get_fundamental_data(code)

        gross_margin = fundamental.get('gross_margin') if fundamental else None
        profit_yoy = fundamental.get('profit_yoy') if fundamental else None

        # debt_ratio: 资产负债率 (越低越好)
        debt_ratio = None
        if fundamental:
            total_assets = fundamental.get('total_assets')
            # 简化: 用净资产收益率反推
            roe = fundamental.get('roe')
            if roe is not None and gross_margin is not None:
                # ROE = 净利/净资产, 毛利率高+ROE低可能高负债
                if roe > 0 and gross_margin > 0:
                    debt_ratio = max(10, min(90, (gross_margin / max(roe, 0.1)) * 5))

        return {
            'gross_margin': gross_margin,
            'profit_yoy': profit_yoy,
            'debt_ratio': round(debt_ratio, 1) if debt_ratio else None,
        }
    except Exception:
        return {'gross_margin': None, 'profit_yoy': None, 'debt_ratio': None}


def _calc_risk_factors(daily_df, benchmark_returns=None):
    """计算风险因子: 波动率, 贝塔"""
    close = daily_df['close'].values
    returns = np.diff(close) / close[:-1]
    returns = returns[~np.isnan(returns)]

    # volatility_20d: 20日日收益率标准差(年化)
    if len(returns) >= 20:
        vol_20d = float(np.std(returns[-20:])) * 100  # 百分比
        vol_annual = vol_20d * np.sqrt(252)
    else:
        vol_annual = None

    # beta_60d: 60日贝塔 (如果有基准数据)
    beta = None
    if len(returns) >= 60 and benchmark_returns is not None and len(benchmark_returns) >= 60:
        try:
            min_len = min(len(returns), len(benchmark_returns))
            pr = returns[-min_len:]
            br = benchmark_returns[-min_len:]
            valid = ~(np.isnan(pr) | np.isnan(br))
            pr, br = pr[valid], br[valid]
            if len(pr) >= 20:
                cov = np.cov(pr, br)[0, 1]
                var_b = np.var(br)
                beta = float(cov / var_b) if var_b > 0 else 1.0
        except Exception:
            beta = None

    return {
        'volatility_20d': round(vol_annual, 2) if vol_annual else None,
        'beta_60d': round(beta, 4) if beta else None,
    }


def _calc_turnover_factor(daily_df):
    """计算换手率因子"""
    try:
        if 'turnover' in daily_df.columns:
            turnover_vals = daily_df['turnover'].values
            if len(turnover_vals) >= 5:
                return float(np.mean(turnover_vals[-5:]))
    except Exception:
        pass
    return None


def _calc_relative_strength(code, daily_df):
    """计算相对强度 (vs 上证指数)"""
    try:
        # 获取同期上证指数
        from data_fetchers import get_daily_kline
        sh_df = get_daily_kline('000001', count=60)
        if sh_df is None or len(sh_df) < 20:
            return None

        close = daily_df['close'].values
        sh_close = sh_df['close'].values

        min_len = min(len(close), len(sh_close))
        stock_ret = (close[-1] / close[-min_len] - 1) * 100
        sh_ret = (sh_close[-1] / sh_close[-min_len] - 1) * 100

        return round(stock_ret - sh_ret, 2)
    except Exception:
        return None


def normalize_factor(value, factor_name, factors):
    """将原始因子值映射到 0-100 的标准化分数"""
    if value is None:
        return 50.0  # 缺失给中性分

    if factor_name == 'momentum_20d':
        # -10% ~ +30% -> 0~100, 中轴约5%
        return min(100, max(0, (value + 10) * 2.5))

    elif factor_name == 'rsi_14':
        # RSI 越高越强, 但>70可能超买
        if value >= 70:
            return 60.0
        elif value <= 30:
            return 60.0  # 超卖也是机会
        elif 45 <= value <= 65:
            return 70.0  # 健康区间
        else:
            return 50.0

    elif factor_name == 'volume_ratio':
        # 1.0 为正常, 过高(>3)可能出货, 过低(<0.5)无量
        if 1.0 <= value <= 2.0:
            return 75.0
        elif 0.7 <= value < 1.0:
            return 60.0
        elif 2.0 < value <= 3.0:
            return 55.0
        else:
            return 40.0

    elif factor_name == 'ma_status':
        # 1=多头, -1=混乱, 0=空头
        if value == 1:
            return 85.0
        elif value == -1:
            return 45.0
        else:
            return 20.0

    elif factor_name == 'macd_signal':
        # 1=金叉, -1=死叉, 0=中性
        if value == 1:
            return 80.0
        elif value == -1:
            return 20.0
        else:
            return 50.0

    elif factor_name == 'money_flow_5d':
        # -5 ~ +5 -> 0~100
        return min(100, max(0, (value + 5) * 10))

    elif factor_name == 'pe_percentile':
        # 已经是0-100分位
        return min(100, max(0, value))

    elif factor_name == 'roe':
        # ROE越高越好, >20%优秀, <5%差
        if value >= 20:
            return 90.0
        elif value >= 15:
            return 75.0
        elif value >= 10:
            return 60.0
        elif value >= 5:
            return 40.0
        else:
            return 20.0

    # ═══ v2 新增因子归一化 ═══

    elif factor_name == 'momentum_60d':
        return min(100, max(0, (value + 15) * 2.2))

    elif factor_name == 'momentum_stability':
        # 动量/波动率比值, 越高越稳定
        if value >= 2:
            return 90.0
        elif value >= 1:
            return 75.0
        elif value >= 0.5:
            return 60.0
        elif value >= 0:
            return 45.0
        else:
            return 30.0

    elif factor_name == 'ma_distance':
        # 偏离MA20, 适度偏离(0-10%)好, 过度(>20%)差
        ad = abs(value)
        if ad <= 5:
            return 75.0
        elif ad <= 10:
            return 65.0
        elif ad <= 20:
            return 50.0
        else:
            return 30.0

    elif factor_name == 'bollinger_pos':
        # 布林带位置, 中轨附近最好
        if 30 <= value <= 70:
            return 75.0
        elif 15 <= value < 30 or 70 < value <= 85:
            return 55.0
        else:
            return 35.0

    elif factor_name == 'pb_ratio':
        if value is None:
            return 50.0
        if value <= 1.5:
            return 85.0
        elif value <= 3:
            return 70.0
        elif value <= 5:
            return 55.0
        elif value <= 8:
            return 35.0
        else:
            return 15.0

    elif factor_name == 'earnings_yield':
        if value is None:
            return 50.0
        if value >= 10:
            return 90.0
        elif value >= 5:
            return 75.0
        elif value >= 3:
            return 60.0
        elif value >= 1.5:
            return 40.0
        else:
            return 20.0

    elif factor_name == 'gross_margin':
        if value is None:
            return 50.0
        if value >= 60:
            return 90.0
        elif value >= 40:
            return 75.0
        elif value >= 25:
            return 60.0
        elif value >= 15:
            return 40.0
        else:
            return 20.0

    elif factor_name == 'profit_yoy':
        if value is None:
            return 50.0
        if value >= 50:
            return 90.0
        elif value >= 20:
            return 75.0
        elif value >= 5:
            return 60.0
        elif value >= -10:
            return 40.0
        else:
            return 20.0

    elif factor_name == 'debt_ratio':
        if value is None:
            return 50.0
        if value <= 30:
            return 85.0
        elif value <= 50:
            return 70.0
        elif value <= 70:
            return 45.0
        else:
            return 20.0

    elif factor_name == 'volatility_20d':
        if value is None:
            return 50.0
        if value <= 20:
            return 85.0
        elif value <= 35:
            return 65.0
        elif value <= 50:
            return 45.0
        elif value <= 70:
            return 25.0
        else:
            return 10.0

    elif factor_name == 'beta_60d':
        if value is None:
            return 50.0
        if 0.8 <= value <= 1.2:
            return 70.0
        elif 0.5 <= value < 0.8:
            return 55.0
        elif 1.2 < value <= 1.5:
            return 45.0
        else:
            return 30.0

    elif factor_name == 'turnover_rate':
        if value is None:
            return 50.0
        if 2 <= value <= 8:
            return 75.0
        elif 1 <= value < 2:
            return 55.0
        elif 8 < value <= 15:
            return 50.0
        else:
            return 30.0

    elif factor_name == 'relative_strength':
        if value is None:
            return 50.0
        if value >= 15:
            return 90.0
        elif value >= 5:
            return 75.0
        elif value >= 0:
            return 60.0
        elif value >= -10:
            return 40.0
        else:
            return 20.0

    return 50.0


def multi_factor_score(factors: dict) -> dict:
    """多因子加权评分

    Args:
        factors: calculate_factors() 返回的 factors 字典

    Returns:
        dict: {total_score, breakdown: {factor: {raw, normalized, weighted}}, weights}
    """
    weights = DEFAULT_WEIGHTS.copy()
    total_score = 0.0
    breakdown = {}

    # v2: 直接使用因子原始键名, 每个因子有自己的权重
    for factor_key, weight in weights.items():
        raw_val = factors.get(factor_key)
        normalized = normalize_factor(raw_val, factor_key, factors)
        weighted = normalized * weight

        breakdown[factor_key] = {
            'raw': raw_val,
            'normalized': round(normalized, 2),
            'weight': weight,
            'weighted': round(weighted, 2),
        }
        total_score += weighted

    # 总分缩放到0-100
    total_score = round(total_score, 2)

    return {
        'total_score': total_score,
        'breakdown': breakdown,
        'weights': weights,
    }


def get_stock_rating(code: str) -> dict:
    """一站式获取股票量化评级

    Args:
        code: 股票代码

    Returns:
        dict: {success, code, factors, score, rating, timestamp, error}
    """
    result = {
        'success': False,
        'code': code,
        'timestamp': datetime.now().isoformat(),
        'factors': {},
        'score': {},
        'rating': '',
        'rating_text': '',
        'error': None,
    }

    try:
        factor_result = calculate_factors(code)
        if not factor_result.get('success'):
            result['error'] = factor_result.get('error', '因子计算失败')
            return result

        factors = factor_result['factors']
        score = multi_factor_score(factors)
        total = score['total_score']

        # 评级映射
        if total >= 80:
            rating = 'A'
        elif total >= 65:
            rating = 'B'
        elif total >= 50:
            rating = 'C'
        elif total >= 35:
            rating = 'D'
        else:
            rating = 'E'

        result['success'] = True
        result['factors'] = factors
        result['score'] = score
        result['rating'] = rating
        result['rating_text'] = _rating_descriptions(rating, total, factors)

    except Exception as e:
        result['error'] = str(e)
        traceback.print_exc()

    return result


def _rating_descriptions(rating: str, total: float, factors: dict) -> str:
    """评级文字说明"""
    desc_map = {
        'A': '强烈推荐 — 多因子综合表现优异，技术面和基本面共振向上',
        'B': '推荐 — 多因子表现良好，具备一定投资价值',
        'C': '中性 — 因子表现一般，需要等待更好的时机',
        'D': '谨慎 — 多数因子偏弱，建议观望或减仓',
        'E': '回避 — 因子全面走弱，不建议参与',
    }
    return desc_map.get(rating, '未知')


def get_rating_text(code: str) -> str:
    """生成用于AI prompt注入的评级文本

    Args:
        code: 股票代码

    Returns:
        str: 格式化文本
    """
    result = get_stock_rating(code)

    if not result.get('success'):
        return f"【量化因子评分】股票: {code}\n  数据获取失败: {result.get('error', '未知错误')}\n"

    factors = result['factors']
    score = result['score']
    breakdown = score.get('breakdown', {})

    factor_labels = {
        'momentum_20d': '20日动量',
        'momentum_60d': '60日动量',
        'momentum_stability': '动量稳定性',
        'rsi_14': 'RSI(14)',
        'volume_ratio': '量比',
        'ma_status': '均线排列',
        'macd_signal': 'MACD信号',
        'ma_distance': 'MA偏离',
        'bollinger_pos': '布林位置',
        'money_flow_5d': '5日资金流',
        'turnover_rate': '换手率',
        'relative_strength': '相对强度',
        'pe_percentile': 'PE分位',
        'pb_ratio': '市净率',
        'earnings_yield': '盈利率',
        'roe': 'ROE',
        'gross_margin': '毛利率',
        'profit_yoy': '利润增速',
        'debt_ratio': '负债率',
        'volatility_20d': '波动率',
        'beta_60d': '贝塔',
    }

    lines = [
        f"【量化因子评分】股票: {code}",
        f"  综合得分: {score['total_score']:.1f}/100  评级: {result['rating']} ({result['rating_text']})",
        "",
        "  因子明细:",
    ]

    for key in DEFAULT_WEIGHTS.keys():
        bd = breakdown.get(key, {})
        raw = bd.get('raw', 'N/A')
        norm = bd.get('normalized', 0)
        wt = bd.get('weight', 0)
        label = factor_labels.get(key, key)
        raw_str = f"{raw:.2f}" if isinstance(raw, (int, float)) else str(raw)
        lines.append(f"    {label}: 原始={raw_str}  标准化={norm:.1f}  权重={wt:.0%}  贡献={bd.get('weighted', 0):.1f}")

    lines.append("")
    return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════
# 横截面百分位排名 (实验性)
# ═══════════════════════════════════════════════════════════════

# 全A股因子横截面缓存表
# 固定值: 因子名称 → [百分位阈值, ...]
# 由 update_factor_universe() 每日更新
_factor_cross_sectional_cache = {}

DEFAULT_CROSS_SECTIONAL_THRESHOLDS = {
    'momentum_20d':  [-20, -10, -5, 0, 5, 10, 15, 20, 30],
    'momentum_60d':  [-30, -15, -5, 0, 5, 15, 25, 35, 50],
    'rsi_14':        [20, 25, 30, 35, 40, 50, 60, 65, 70, 75, 80],
    'volume_ratio':  [0.2, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0],
    'volatility_20d': [10, 15, 20, 25, 30, 35, 40, 50, 60, 80],
    'turnover_rate': [0.5, 1, 2, 3, 5, 8, 12, 20, 30],
    'gross_margin':  [10, 15, 20, 25, 30, 40, 50, 60, 70],
    'roe':           [-5, 0, 2, 5, 10, 15, 20, 25, 30],
    'pe_ttm':        [0, 10, 15, 20, 30, 50, 80, 100, 200],
    'pb':            [0.5, 1, 1.5, 2, 3, 5, 8, 12, 20],
    'profit_yoy':    [-50, -20, -5, 0, 10, 20, 30, 50, 100],
    'debt_ratio':    [5, 10, 20, 30, 40, 50, 60, 70, 80],
    'beta_60d':      [0.2, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0],
}


def normalize_cross_sectional(raw_value: float, factor_name: str) -> float:
    """
    基于百分位阈值将原始因子值映射到0-100分
    使用预计算的全A股横截面分布 (更精确的校准请用 update_factor_universe)
    """
    thresholds = DEFAULT_CROSS_SECTIONAL_THRESHOLDS.get(factor_name, [])
    if not thresholds or raw_value is None:
        return 50.0  # 无阈值时返回中性分

    try:
        raw_value = float(raw_value)
    except (ValueError, TypeError):
        return 50.0

    # 二分查找: 值在阈值数组中的位置 = 百分位
    # 阈值数组按升序排列, 每个位置代表一个百分位档次
    import bisect
    idx = bisect.bisect_left(thresholds, raw_value)
    percentile = (idx / len(thresholds)) * 100
    return round(percentile, 1)


def update_factor_universe():
    """
    更新全A股因子横截面分布 (每日盘后运行)
    扫描所有A股的因子值, 计算每个因子的十分位阈值, 保存到缓存
    此函数较耗时 (需遍历全A股), 建议在调度器中每日运行一次
    """
    try:
        from models import SessionLocal
        from db import get_latest_financial
        import random

        db = SessionLocal()
        codes = []
        try:
            # 获取股票列表 (取代表性的200只作为样本)
            from data_fetchers import get_daily_kline
            # 先尝试从缓存获取股票列表
            import json, os
            cache_path = os.path.join(os.path.dirname(__file__), 'stock_list_cache.json')
            if os.path.exists(cache_path):
                with open(cache_path) as f:
                    stock_list = json.load(f)
                    codes = [s.get('code', '') for s in stock_list if s.get('code')]
                # 随机采样200只
                if len(codes) > 200:
                    random.seed(42)
                    codes = random.sample(codes, 200)
        except Exception:
            pass
        finally:
            db.close()

        if not codes:
            return {'success': False, 'error': '无法获取股票列表'}

        # 对每个因子收集全样本数据
        factor_data = {name: [] for name in DEFAULT_CROSS_SECTIONAL_THRESHOLDS}
        for code in codes:
            try:
                result = calculate_factors(code)
                if result.get('success'):
                    for name in factor_data:
                        val = result['factors'].get(name)
                        if val is not None:
                            factor_data[name].append(float(val))
            except Exception:
                continue

        # 计算每个因子的十分位阈值
        import numpy as np
        new_thresholds = {}
        for name, values in factor_data.items():
            if len(values) >= 30:
                arr = np.array(values)
                arr = arr[~np.isnan(arr)]
                if len(arr) >= 30:
                    percentiles = np.percentile(arr, [10, 20, 30, 40, 50, 60, 70, 80, 90])
                    new_thresholds[name] = [round(float(p), 4) for p in percentiles]

        # 更新全局缓存
        if new_thresholds:
            global _factor_cross_sectional_cache
            _factor_cross_sectional_cache = new_thresholds

        return {'success': True, 'updated_factors': len(new_thresholds), 'sample_size': len(codes)}

    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_feature_vector(code: str) -> dict:
    """
    Extract a DL-ready feature vector for a single stock.
    Uses the existing 20-factor compute path, returns numpy arrays for DL models.
    Returns dict with keys: daily_features (30, 20), fundamental_features (6,).
    Returns None if insufficient data.
    """
    from data_fetchers import get_daily_kline, get_money_flow_history, get_fundamental_data
    from dl_models.features import build_daily_features, DAILY_FEATURE_NAMES
    import logging

    logger = logging.getLogger(__name__)

    try:
        # Fetch daily K-line (60 days for sufficient history)
        daily = get_daily_kline(code, count=60)
        if daily is None or len(daily) < 30:
            return None

        close = daily['close'].values.astype(np.float32)
        open_arr = daily['open'].values.astype(np.float32)
        high = daily['high'].values.astype(np.float32)
        low = daily['low'].values.astype(np.float32)
        volume = daily['volume'].values.astype(np.float32)
        amount = daily.get('amount', volume * close)
        if hasattr(amount, 'values'):
            amount = amount.values.astype(np.float32)
        else:
            amount = np.array(amount, dtype=np.float32)

        # Money flow
        mf_5d, mf_10d = None, None
        try:
            mf = get_money_flow_history(code, count=60)
            if mf is not None:
                mf_5d = mf['net_inflow'].rolling(5).mean().values.astype(np.float32)
                mf_10d = mf['net_inflow'].rolling(10).mean().values.astype(np.float32)
        except Exception:
            pass

        daily_features = build_daily_features(
            open_arr, high, low, close, volume, amount,
            money_flow_5d=mf_5d, money_flow_10d=mf_10d,
        )

        # Convert to array matrix (T, F) with named order
        feat_matrix = np.column_stack([
            daily_features.get(name, np.full(len(close), np.nan, dtype=np.float32))
            for name in DAILY_FEATURE_NAMES
        ]).astype(np.float32)

        # Drop NaN rows (warmup periods)
        valid_mask = ~np.isnan(feat_matrix).any(axis=1)
        feat_matrix = feat_matrix[valid_mask]

        # Keep last 30 rows
        if len(feat_matrix) > 30:
            feat_matrix = feat_matrix[-30:]

        # Fundamental features
        fund_features = np.zeros(6, dtype=np.float32)
        try:
            fund = get_fundamental_data(code)
            if fund is not None:
                fund_features = np.array([
                    float(fund.get('pe_ttm', 0) or 0),
                    float(fund.get('pb', 0) or 0),
                    float(fund.get('roe', 0) or 0),
                    float(fund.get('gross_margin', 0) or 0),
                    float(fund.get('revenue_yoy', 0) or 0),
                    float(fund.get('debt_ratio', 0) or 0),
                ], dtype=np.float32)
        except Exception:
            pass

        return {
            'daily_features': feat_matrix,
            'fundamental_features': fund_features,
        }
    except Exception as e:
        logger.warning(f"get_feature_vector({code}) failed: {e}")
        return None


if __name__ == '__main__':
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else '300433'
    text = get_rating_text(code)
    logger.info(f"因子评级输出:\n{text}")
    print(text)  # CLI 输出
