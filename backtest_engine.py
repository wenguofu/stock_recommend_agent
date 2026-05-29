#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回测引擎 — 使用历史K线数据评估量化策略表现"""

import math
import traceback
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════
# 技术指标计算
# ═══════════════════════════════════════════════════════════════

def calc_sma(series: np.ndarray, period: int) -> np.ndarray:
    """简单移动平均"""
    result = np.full_like(series, np.nan)
    for i in range(period - 1, len(series)):
        result[i] = np.nanmean(series[i - period + 1:i + 1])
    return result


def calc_ema(series: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均（跳过NaN）"""
    result = np.full_like(series, np.nan)
    multiplier = 2.0 / (period + 1)
    # 找到第一个非NaN的起始位置
    first_valid = np.where(~np.isnan(series))[0]
    if len(first_valid) == 0:
        return result
    start = first_valid[0]
    # 从有足够数据的点开始计算
    calc_start = max(start + period - 1, period - 1)
    if calc_start >= len(series):
        return result
    result[calc_start] = np.nanmean(series[calc_start - period + 1:calc_start + 1])
    for i in range(calc_start + 1, len(series)):
        if np.isnan(series[i]):
            continue
        result[i] = (series[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def calc_rsi(series: np.ndarray, period: int = 14) -> np.ndarray:
    """相对强弱指标 RSI"""
    result = np.full_like(series, np.nan)
    deltas = np.diff(series)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.full_like(series, np.nan)
    avg_loss = np.full_like(series, np.nan)
    avg_gain[period] = np.nanmean(gains[:period])
    avg_loss[period] = np.nanmean(losses[:period])
    for i in range(period + 1, len(series)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i - 1]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i - 1]) / period
    for i in range(period, len(series)):
        if avg_loss[i] == 0:
            result[i] = 100
        else:
            rs = avg_gain[i] / avg_loss[i]
            result[i] = 100 - (100 / (1 + rs))
    return result


def calc_macd(series: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD指标"""
    ema_fast = calc_ema(series, fast)
    ema_slow = calc_ema(series, slow)
    dif = ema_fast - ema_slow
    dea = calc_ema(dif, signal)
    macd_hist = 2 * (dif - dea)
    return dif, dea, macd_hist


def calc_bollinger(series: np.ndarray, period: int = 20, std_dev: float = 2.0):
    """布林带"""
    ma = calc_sma(series, period)
    std = np.full_like(series, np.nan)
    for i in range(period - 1, len(series)):
        std[i] = np.std(series[i - period + 1:i + 1])
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    return upper, ma, lower


# ═══════════════════════════════════════════════════════════════
# 支持的策略预设
# ═══════════════════════════════════════════════════════════════

STRATEGY_PRESETS = {
    "ma_cross": {
        "name": "均线金叉策略",
        "description": "短期均线上穿长期均线买入，下穿卖出。适合趋势明确的市场，震荡市中假信号较多。推荐参数：5/20（短线），10/60（中线）",
        "params": [
            {"key": "fast_period", "label": "短期均线", "type": "int", "default": 5, "min": 2, "max": 60},
            {"key": "slow_period", "label": "长期均线", "type": "int", "default": 20, "min": 5, "max": 120},
        ],
    },
    "rsi_reversal": {
        "name": "RSI超买超卖策略",
        "description": "RSI低于超卖线买入（超跌反弹），高于超买线卖出（高位回落）。适合震荡市，强趋势市中会过早离场。推荐：超卖30/超买70",
        "params": [
            {"key": "rsi_period", "label": "RSI周期", "type": "int", "default": 14, "min": 5, "max": 30},
            {"key": "oversold", "label": "超卖线", "type": "int", "default": 30, "min": 10, "max": 45},
            {"key": "overbought", "label": "超买线", "type": "int", "default": 70, "min": 55, "max": 90},
        ],
    },
    "macd_cross": {
        "name": "MACD金叉死叉策略",
        "description": "DIF上穿DEA金叉买入，下穿死叉卖出。中长线趋势策略，信号较均线金叉更平滑但滞后性更强。经典参数：12/26/9",
        "params": [
            {"key": "fast", "label": "快线周期", "type": "int", "default": 12, "min": 5, "max": 30},
            {"key": "slow", "label": "慢线周期", "type": "int", "default": 26, "min": 10, "max": 60},
            {"key": "signal", "label": "信号周期", "type": "int", "default": 9, "min": 5, "max": 20},
        ],
    },
    "bollinger_break": {
        "name": "布林带突破策略",
        "description": "价格跌破下轨买入（超卖反弹），突破上轨卖出（超买回落）。震荡市中效果好，趋势突破时容易错过大行情。推荐：20日/2倍标准差",
        "params": [
            {"key": "period", "label": "布林周期", "type": "int", "default": 20, "min": 10, "max": 60},
            {"key": "std_dev", "label": "标准差倍数", "type": "float", "default": 2.0, "min": 1.0, "max": 3.5},
        ],
    },
    "sar_parabolic": {
        "name": "SAR抛物线转向",
        "description": "价格上穿SAR买入，下穿SAR卖出。强趋势市中效果极佳，跟随趋势直到反转。震荡市中频繁止损。需配合趋势过滤",
        "params": [
            {"key": "acceleration", "label": "加速因子", "type": "float", "default": 0.02, "min": 0.005, "max": 0.1},
            {"key": "maximum", "label": "最大加速", "type": "float", "default": 0.2, "min": 0.1, "max": 0.5},
        ],
    },
    "adx_trend": {
        "name": "ADX趋势跟踪",
        "description": "ADX>25表示强趋势，顺势开仓；ADX<20表示无趋势，平仓观望。先过滤趋势再交易，比纯均线策略更稳健。推荐阈值：25",
        "params": [
            {"key": "adx_period", "label": "ADX周期", "type": "int", "default": 14, "min": 7, "max": 30},
            {"key": "threshold", "label": "趋势阈值", "type": "int", "default": 25, "min": 15, "max": 35},
        ],
    },
    "stoch_kd": {
        "name": "KDJ随机指标",
        "description": "K<20超卖买入，K>80超买卖出。对短期波动敏感，适合震荡市做波段。不适合单边趋势市（会反复打脸）。推荐：9/20/80",
        "params": [
            {"key": "k_period", "label": "K周期", "type": "int", "default": 9, "min": 5, "max": 21},
            {"key": "oversold", "label": "超卖线", "type": "int", "default": 20, "min": 10, "max": 35},
            {"key": "overbought", "label": "超买线", "type": "int", "default": 80, "min": 65, "max": 90},
        ],
    },
    "triple_ma": {
        "name": "三均线系统",
        "description": "快>中>慢多头排列买入，快<中<慢空头排列卖出。经典趋势系统，信号少但质量高。大周期大趋势不会错过。推荐：5/13/34（斐波那契数列）",
        "params": [
            {"key": "fast", "label": "快线", "type": "int", "default": 5, "min": 3, "max": 20},
            {"key": "mid", "label": "中线", "type": "int", "default": 13, "min": 8, "max": 40},
            {"key": "slow", "label": "慢线", "type": "int", "default": 34, "min": 20, "max": 120},
        ],
    },
    "vwap_trend": {
        "name": "VWAP均价趋势",
        "description": "价格在VWAP上方+VWAP上行=强势买入；价格跌破VWAP或VWAP走平=卖出。机构常用基准，日内和短线效果最佳",
        "params": [
            {"key": "vwap_period", "label": "VWAP周期", "type": "int", "default": 20, "min": 5, "max": 60},
        ],
    },
}


# ═══════════════════════════════════════════════════════════════
# 信号生成
# ═══════════════════════════════════════════════════════════════

def generate_signals(df: pd.DataFrame, strategy_type: str, params: Dict[str, Any]) -> np.ndarray:
    """
    生成交易信号
    返回: -1=卖出, 0=持有, 1=买入
    """
    close = df['close'].values
    signals = np.zeros(len(df))

    if strategy_type == "ma_cross":
        fast = calc_sma(close, params.get('fast_period', 5))
        slow = calc_sma(close, params.get('slow_period', 20))
        for i in range(1, len(df)):
            if not np.isnan(fast[i]) and not np.isnan(slow[i]):
                if fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]:
                    signals[i] = 1  # 金叉买入
                elif fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]:
                    signals[i] = -1  # 死叉卖出

    elif strategy_type == "rsi_reversal":
        rsi = calc_rsi(close, params.get('rsi_period', 14))
        oversold = params.get('oversold', 30)
        overbought = params.get('overbought', 70)
        for i in range(1, len(df)):
            if not np.isnan(rsi[i]):
                if rsi[i - 1] <= oversold and rsi[i] > oversold:
                    signals[i] = 1  # 脱离超卖买入
                elif rsi[i - 1] >= overbought and rsi[i] < overbought:
                    signals[i] = -1  # 脱离超买卖出

    elif strategy_type == "macd_cross":
        dif, dea, _ = calc_macd(close, params.get('fast', 12), params.get('slow', 26), params.get('signal', 9))
        for i in range(1, len(df)):
            if not np.isnan(dif[i]) and not np.isnan(dea[i]):
                if dif[i - 1] <= dea[i - 1] and dif[i] > dea[i]:
                    signals[i] = 1  # 金叉买入
                elif dif[i - 1] >= dea[i - 1] and dif[i] < dea[i]:
                    signals[i] = -1  # 死叉卖出

    elif strategy_type == "bollinger_break":
        upper, ma, lower = calc_bollinger(close, params.get('period', 20), params.get('std_dev', 2.0))
        for i in range(1, len(df)):
            if not np.isnan(upper[i]):
                if close[i - 1] >= lower[i - 1] and close[i] < lower[i]:
                    signals[i] = 1  # 跌破下轨买入
                elif close[i - 1] <= upper[i - 1] and close[i] > upper[i]:
                    signals[i] = -1  # 突破上轨卖出

    elif strategy_type == "sar_parabolic":
        try:
            import talib
            _has_talib = True
        except ImportError:
            _has_talib = False
        if not _has_talib:
            print("[回测] talib未安装，跳过sar_parabolic策略")
            return signals
        acc = params.get('acceleration', 0.02)
        maximum = params.get('maximum', 0.2)
        sar = talib.SAR(df['high'].values, df['low'].values, acceleration=acc, maximum=maximum)
        for i in range(1, len(df)):
            if not np.isnan(sar[i]):
                if close[i - 1] <= sar[i - 1] and close[i] > sar[i]:
                    signals[i] = 1
                elif close[i - 1] >= sar[i - 1] and close[i] < sar[i]:
                    signals[i] = -1

    elif strategy_type == "adx_trend":
        try:
            import talib
            _has_talib = True
        except ImportError:
            _has_talib = False
        if not _has_talib:
            print("[回测] talib未安装，跳过adx_trend策略")
            return signals
        period = params.get('adx_period', 14)
        thresh = params.get('threshold', 25)
        high, low, close_a = df['high'].values, df['low'].values, df['close'].values
        adx = talib.ADX(high, low, close_a, timeperiod=period)
        plus_di = talib.PLUS_DI(high, low, close_a, timeperiod=period)
        minus_di = talib.MINUS_DI(high, low, close_a, timeperiod=period)
        for i in range(1, len(df)):
            if not np.isnan(adx[i]) and not np.isnan(plus_di[i]):
                if adx[i] > thresh and plus_di[i] > minus_di[i] and (adx[i - 1] <= thresh or plus_di[i - 1] <= minus_di[i - 1]):
                    signals[i] = 1
                elif adx[i] < thresh * 0.8 or (minus_di[i] > plus_di[i] and adx[i] > thresh):
                    signals[i] = -1

    elif strategy_type == "stoch_kd":
        try:
            import talib
            _has_talib = True
        except ImportError:
            _has_talib = False
        if not _has_talib:
            print("[回测] talib未安装，跳过stoch_kd策略")
            return signals
        k_period = params.get('k_period', 9)
        oversold = params.get('oversold', 20)
        overbought = params.get('overbought', 80)
        slowk, slowd = talib.STOCH(df['high'].values, df['low'].values, df['close'].values,
                                    fastk_period=k_period, slowk_period=3, slowk_matype=0,
                                    slowd_period=3, slowd_matype=0)
        for i in range(1, len(df)):
            if not np.isnan(slowk[i]):
                if slowk[i - 1] <= oversold and slowk[i] > oversold:
                    signals[i] = 1
                elif slowk[i - 1] >= overbought and slowk[i] < overbought:
                    signals[i] = -1

    elif strategy_type == "triple_ma":
        fast_p = params.get('fast', 5)
        mid_p = params.get('mid', 13)
        slow_p = params.get('slow', 34)
        ma_fast = calc_sma(close, fast_p)
        ma_mid = calc_sma(close, mid_p)
        ma_slow = calc_sma(close, slow_p)
        for i in range(1, len(df)):
            if not np.isnan(ma_slow[i]):
                prev_bull = ma_fast[i - 1] > ma_mid[i - 1] > ma_slow[i - 1]
                curr_bull = ma_fast[i] > ma_mid[i] > ma_slow[i]
                if not prev_bull and curr_bull:
                    signals[i] = 1
                prev_bear = ma_fast[i - 1] < ma_mid[i - 1] < ma_slow[i - 1]
                curr_bear = ma_fast[i] < ma_mid[i] < ma_slow[i]
                if not prev_bear and curr_bear:
                    signals[i] = -1

    elif strategy_type == "vwap_trend":
        period = params.get('vwap_period', 20)
        # VWAP ≈ 价格×成交量 / 成交量的滚动均值
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).rolling(period).sum() / df['volume'].rolling(period).sum()
        vwap_ma = vwap.rolling(5).mean()
        for i in range(1, len(df)):
            if not pd.isna(vwap.iloc[i]) and not pd.isna(vwap_ma.iloc[i]):
                prev_vwap = vwap.iloc[i - 1]
                curr_vwap = vwap.iloc[i]
                if close[i] > curr_vwap and curr_vwap > prev_vwap and close[i - 1] <= prev_vwap:
                    signals[i] = 1
                elif close[i] < curr_vwap or curr_vwap < prev_vwap:
                    signals[i] = -1

    return signals


# ═══════════════════════════════════════════════════════════════
# 回测主函数
# ═══════════════════════════════════════════════════════════════

def run_backtest(
    code: str,
    strategy_type: str,
    params: Dict[str, Any],
    initial_capital: float = 100000,
    start_date: str = None,
    end_date: str = None,
    max_data_days: int = 720,
) -> Dict[str, Any]:
    """
    执行回测
    Args:
        code: 股票代码
        strategy_type: 策略类型 (ma_cross, rsi_reversal, macd_cross, bollinger_break)
        params: 策略参数
        initial_capital: 初始资金
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD
        max_data_days: 最大获取天数
    Returns:
        dict with: trades, equity_curve, metrics
    """
    from data_fetchers import get_daily_kline

    # 1. 获取数据
    df = get_daily_kline(code, count=max_data_days)
    if df is None or df.empty:
        return {"success": False, "error": f"无法获取 {code} 的历史K线数据"}

    # 2. 过滤日期范围
    if start_date:
        df = df[df['date'] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df['date'] <= pd.Timestamp(end_date)]
    if len(df) < 30:
        return {"success": False, "error": f"数据不足30个交易日（当前{len(df)}天），请扩大回测范围"}

    df = df.reset_index(drop=True)

    # 3. 生成信号
    signals = generate_signals(df, strategy_type, params)

    # 信号时移：第i天收盘后生成的信号，在第i+1天开盘执行
    signals_shifted = np.zeros(len(df))
    signals_shifted[1:] = signals[:-1]
    signals = signals_shifted

    # 滑点参数 (bp)
    slippage_bps = params.get('slippage_bps', 10)

    # 4. 模拟交易
    cash = initial_capital
    shares = 0
    trades = []
    equity_curve = []

    for i in range(1, len(df)):  # 从第1天开始 (跳过第0天, 因为信号需要时移)
        row = df.iloc[i]
        price = row['close']
        date_str = str(row['date'])[:10]
        signal = signals[i]

        # 第i天开盘执行前一天收盘后生成的信号
        open_price = row['open']

        if signal == 1 and cash > 0:
            # 买入：全仓
            # 加入滑点 (买方不利方向)
            exec_price = open_price * (1 + slippage_bps / 10000)
            can_buy = int(cash / exec_price / 100) * 100
            if can_buy >= 100:
                cost = can_buy * exec_price
                commission = max(cost * 0.00025, 5)
                cash -= (cost + commission)
                shares += can_buy
                trades.append({
                    'date': date_str, 'type': 'buy', 'price': round(exec_price, 2),
                    'shares': can_buy, 'cost': round(cost, 2),
                    'commission': round(commission, 2),
                    'slippage': round(can_buy * (exec_price - open_price), 2),
                    'cash_after': round(cash, 2),
                })

        elif signal == -1 and shares > 0:
            # 卖出：清仓
            # 加入滑点 (卖方不利方向)
            exec_price = open_price * (1 - slippage_bps / 10000)
            proceeds = shares * exec_price
            commission = max(proceeds * 0.00025, 5)
            tax = proceeds * 0.001
            cash += (proceeds - commission - tax)
            trades.append({
                'date': date_str, 'type': 'sell', 'price': round(exec_price, 2),
                'shares': shares, 'proceeds': round(proceeds, 2),
                'commission': round(commission, 2), 'tax': round(tax, 2),
                'slippage': round(shares * (open_price - exec_price), 2),
                'cash_after': round(cash, 2),
            })
            shares = 0

        # 记录每日净值
        market_value = shares * price
        total_value = cash + market_value
        equity_curve.append({
            'date': date_str,
            'total_value': round(total_value, 2),
            'cash': round(cash, 2),
            'market_value': round(market_value, 2),
            'shares': shares,
        })

    # 5. 计算指标
    values = np.array([e['total_value'] for e in equity_curve])
    dates = [e['date'] for e in equity_curve]

    total_return = (values[-1] - initial_capital) / initial_capital * 100 if initial_capital > 0 else 0

    # 最大回撤
    peak = np.maximum.accumulate(values)
    drawdown = (values - peak) / peak * 100
    max_drawdown = float(np.min(drawdown))

    # 年化收益率
    trading_days = len(values)
    years = trading_days / 252
    if years > 0 and values[-1] > 0 and values[0] > 0:
        annual_return = (pow(values[-1] / values[0], 1 / years) - 1) * 100
    else:
        annual_return = 0.0

    # 夏普比率
    daily_returns = np.diff(values) / values[:-1]
    if len(daily_returns) > 0:
        sharpe = float(np.mean(daily_returns) / (np.std(daily_returns) + 1e-10) * np.sqrt(252))
    else:
        sharpe = 0.0

    # 胜率
    if len(trades) >= 2:
        buys = [t for t in trades if t['type'] == 'buy']
        sells = [t for t in trades if t['type'] == 'sell']
        wins = 0
        total_trades = min(len(buys), len(sells))
        for j in range(total_trades):
            buy_price = buys[j]['price']
            sell_price = sells[j]['price']
            if sell_price > buy_price:
                wins += 1
        win_rate = wins / total_trades * 100 if total_trades > 0 else 0
    else:
        total_trades = 0
        win_rate = 0

    # 交易频率
    avg_hold_days = 0
    if len(trades) >= 4:
        hold_days = []
        for j in range(0, len(trades) - 1, 2):
            if trades[j]['type'] == 'buy' and trades[j + 1]['type'] == 'sell':
                try:
                    d1 = datetime.strptime(trades[j]['date'], '%Y-%m-%d')
                    d2 = datetime.strptime(trades[j + 1]['date'], '%Y-%m-%d')
                    hold_days.append((d2 - d1).days)
                except:
                    pass
        avg_hold_days = np.mean(hold_days) if hold_days else 0

    # 买入持有收益（基准）
    buy_hold_return = (df['close'].values[-1] - df['close'].values[0]) / df['close'].values[0] * 100

    # 信号分布
    buy_signals = int(np.sum(signals == 1))
    sell_signals = int(np.sum(signals == -1))

    return {
        "success": True,
        "code": code,
        "strategy": strategy_type,
        "params": params,
        "period": {
            "start": dates[0],
            "end": dates[-1],
            "trading_days": trading_days,
        },
        "initial_capital": initial_capital,
        "final_value": round(float(values[-1]), 2),
        "metrics": {
            "total_return": round(total_return, 2),
            "annual_return": round(annual_return, 2),
            "max_drawdown": round(max_drawdown, 2),
            "sharpe_ratio": round(sharpe, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": total_trades,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "avg_hold_days": round(avg_hold_days, 1),
            "buy_hold_return": round(buy_hold_return, 2),
            "excess_return": round(total_return - buy_hold_return, 2),
        },
        "trades": trades,
        "equity_curve": equity_curve,
    }


def run_forecast(code: str, strategy_type: str, params: dict, forecast_days: int = 22) -> dict:
    """预测未来N个交易日多场景下的买卖信号"""
    from data_fetchers import get_daily_kline
    from datetime import date as dt_date, timedelta
    import math

    df = get_daily_kline(code, count=240)
    if df is None or df.empty:
        return {"success": False, "error": f"无法获取 {code} 的历史数据"}

    close = df['close'].values
    signals = generate_signals(df, strategy_type, params)

    # 最新信号
    last_signal = 0
    for i in range(len(signals) - 1, -1, -1):
        if signals[i] != 0:
            last_signal = int(signals[i])
            break

    # 历史波动率
    returns = np.diff(close) / close[:-1]
    daily_vol = float(np.std(returns)) if len(returns) > 0 else 0.02
    last_price = float(close[-1])
    last_date = str(df['date'].iloc[-1])[:10]
    try:
        last_dt = datetime.strptime(last_date, '%Y-%m-%d').date()
    except:
        last_dt = dt_date.today() - timedelta(days=1)

    # 策略指标预计算（所有场景共享）
    indicators = {}
    if strategy_type == "ma_cross":
        fp = params.get('fast_period', 5)
        sp = params.get('slow_period', 20)
        indicators['ma_fast'] = calc_sma(close, fp)
        indicators['ma_slow'] = calc_sma(close, sp)
    elif strategy_type == "rsi_reversal":
        indicators['rsi'] = calc_rsi(close, params.get('rsi_period', 14))
    elif strategy_type == "macd_cross":
        d, dea, _ = calc_macd(close, params.get('fast', 12), params.get('slow', 26), params.get('signal', 9))
        indicators['dif'] = d; indicators['dea'] = dea
    elif strategy_type == "bollinger_break":
        period = params.get('period', 20)
        std = params.get('std_dev', 2.0)
        u, m, l = calc_bollinger(close, period, std)
        indicators['upper'] = u; indicators['mid'] = m; indicators['lower'] = l
    elif strategy_type == "sar_parabolic":
        try:
            import talib
            indicators['sar'] = talib.SAR(df['high'].values, df['low'].values,
                acceleration=params.get('acceleration', 0.02), maximum=params.get('maximum', 0.2))
        except ImportError:
            return {"success": False, "error": "SAR需要TA-Lib"}

    def get_latest(arr):
        v = arr[~np.isnan(arr)]
        return float(v[-1]) if len(v) > 0 else 0

    def calc_signal_at_price(price, indicators, last_dir):
        """给定当前价格和历史指标，判断策略信号"""
        if strategy_type == "ma_cross":
            # 假设MA随时间缓慢移动
            diff = get_latest(indicators['ma_fast']) - get_latest(indicators['ma_slow'])
            if diff > 0:
                return 1 if last_dir != -1 else 0
            else:
                return -1 if last_dir != 1 else 0
        elif strategy_type == "rsi_reversal":
            oversold = params.get('oversold', 30)
            overbought = params.get('overbought', 70)
            curr = get_latest(indicators['rsi'])
            proj = curr * 0.97 + 50 * 0.03
            if proj <= oversold: return 1
            if proj >= overbought: return -1
            return 0
        elif strategy_type == "macd_cross":
            d = get_latest(indicators['dif'])
            de = get_latest(indicators['dea'])
            if d > de: return 1 if last_dir != -1 else 0
            return -1 if last_dir != 1 else 0
        elif strategy_type == "bollinger_break":
            u = get_latest(indicators['upper'])
            l = get_latest(indicators['lower'])
            m = get_latest(indicators['mid'])
            if price <= l: return 1
            if price >= u: return -1
            return 0
        elif strategy_type == "sar_parabolic":
            s = get_latest(indicators['sar'])
            if price > s: return 1 if last_dir != -1 else 0
            return -1 if last_dir != 1 else 0
        return 0

    # 场景定义：(日涨幅, 波动大小, 名称, 描述)
    scenarios_config = [
        (0.012, 0.015, "单边上涨", "价格持续上行，趋势强劲"),
        (-0.01, 0.015, "单边下跌", "价格持续下行，趋势偏空"),
        (0.004, 0.025, "震荡上涨", "价格波动上行，震荡走高"),
        (-0.003, 0.025, "震荡下跌", "价格波动下行，震荡走低"),
        (0.0, 0.018, "横盘震荡", "价格区间整理，方向不明"),
    ]

    scenarios = []
    for daily_trend, noise_amp, name, desc in scenarios_config:
        next_date = last_dt + timedelta(days=1)
        predictions = []
        dir_signal = last_signal

        for day_idx in range(forecast_days):
            while next_date.weekday() >= 5:
                next_date += timedelta(days=1)
            ds = next_date.strftime('%Y-%m-%d')

            # 确定性趋势 + 小幅随机噪声
            trend_factor = 1.0 + daily_trend
            noise = np.random.uniform(-noise_amp, noise_amp)
            price = last_price * (trend_factor ** (day_idx + 1)) * (1 + noise)
            price = round(max(price, last_price * 0.3), 2)
            price = round(min(price, last_price * 5.0), 2)

            # 计算信号
            sig = calc_signal_at_price(price, indicators, dir_signal)
            if sig != 0:
                dir_signal = sig

            action = '买入' if sig == 1 else ('卖出' if sig == -1 else '持有')
            predictions.append({
                'date': ds, 'price': round(price, 2),
                'signal': sig, 'action': action,
            })
            next_date += timedelta(days=1)

        # 场景指标
        start_p = predictions[0]['price']
        end_p = predictions[-1]['price']
        ret = (end_p - start_p) / start_p * 100
        prices_arr = np.array([p['price'] for p in predictions])
        peak = np.maximum.accumulate(prices_arr)
        dd = (prices_arr - peak) / peak * 100
        max_dd = float(np.min(dd))

        # 交易统计
        buys = sum(1 for p in predictions if p['signal'] == 1)
        sells = sum(1 for p in predictions if p['signal'] == -1)
        trades = min(buys, sells)

        scenarios.append({
            'name': name, 'description': desc,
            'drift': daily_trend, 'vol_mult': noise_amp,
            'metrics': {
                'return': round(ret, 2),
                'max_drawdown': round(max_dd, 2),
                'trades': trades,
                'buy_signals': buys,
                'sell_signals': sells,
            },
            'prediction': predictions,
        })

    return {
        "success": True,
        "code": code,
        "strategy": strategy_type,
        "params": params,
        "last_price": last_price,
        "last_date": last_date,
        "current_signal": '买入' if last_signal == 1 else ('卖出' if last_signal == -1 else '持有'),
        "forecast_days": forecast_days,
        "scenarios": scenarios,
    }
