#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Market Trend Monitor — 大盘趋势监控引擎"""

import pandas as pd
import numpy as np
from data_fetchers import get_daily_kline


def _ema(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing EMA.

    Uses SMA of first `period` values as seed, then:
        EMA_t = price_t * (1/period) + EMA_{t-1} * (1 - 1/period)
    """
    result = pd.Series([np.nan] * len(series), index=series.index)
    if len(series) < period:
        return result
    alpha = 1.0 / period
    # SMA seed
    result.iloc[period - 1] = series.iloc[:period].mean()
    for i in range(period, len(series)):
        result.iloc[i] = series.iloc[i] * alpha + result.iloc[i - 1] * (1 - alpha)
    return result


def get_index_kline(code: str = 'sh000001', days: int = 180) -> pd.DataFrame:
    """获取指数日K线数据"""
    return get_daily_kline(code, count=days)


def check_adx_trend(df: pd.DataFrame, period: int = 14, threshold: float = 25.0) -> dict:
    """ADX 趋势判断。

    Returns:
        {score, signal(bullish|bearish|neutral), detail, adx, plus_di, minus_di}
    """
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    n = len(df)

    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        )
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Wilder's smoothing
    tr_smooth = _ema(pd.Series(tr), period).values
    plus_dm_smooth = _ema(pd.Series(plus_dm), period).values
    minus_dm_smooth = _ema(pd.Series(minus_dm), period).values

    # +DI and -DI
    plus_di = np.where(tr_smooth > 0, 100.0 * plus_dm_smooth / tr_smooth, 0)
    minus_di = np.where(tr_smooth > 0, 100.0 * minus_dm_smooth / tr_smooth, 0)

    # DX
    di_sum = plus_di + minus_di
    dx = np.where(di_sum > 0, 100.0 * np.abs(plus_di - minus_di) / di_sum, 0)

    # ADX = Wilder's smoothed DX
    adx_series = _ema(pd.Series(dx), period)
    adx_val = float(adx_series.iloc[-1]) if not np.isnan(adx_series.iloc[-1]) else 0.0
    plus_di_val = float(plus_di[-1])
    minus_di_val = float(minus_di[-1])

    if adx_val > threshold:
        if minus_di_val > plus_di_val:
            signal = 'bearish'
            score = 25
        else:
            signal = 'bullish'
            score = 0
    else:
        signal = 'neutral'
        score = 0

    return {
        'score': score,
        'signal': signal,
        'signals': [signal] if signal != 'neutral' else [],
        'detail': f'ADX={adx_val:.1f} +DI={plus_di_val:.1f} -DI={minus_di_val:.1f}',
        'adx': round(adx_val, 2),
        'plus_di': round(plus_di_val, 2),
        'minus_di': round(minus_di_val, 2),
    }


def _sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def check_ma_pattern(df: pd.DataFrame) -> dict:
    """均线形态分析。

    Returns:
        {score, signals[], ma20, ma60, ma120}
    """
    close = df['close']
    ma20_val = float(_sma(close, 20).iloc[-1])
    ma60_val = float(_sma(close, 60).iloc[-1])
    ma120_val = float(_sma(close, 120).iloc[-1])
    cur_price = float(close.iloc[-1])

    signals = []
    score = 0

    # MA20 < MA60 → death_cross +20
    if ma20_val < ma60_val:
        signals.append('death_cross')
        score += 20

    # Price < MA120 → price_below_ma120 +15
    if cur_price < ma120_val:
        signals.append('price_below_ma120')
        score += 15

    # MA20 < MA60 < MA120 → bearish_alignment +25
    if ma20_val < ma60_val < ma120_val:
        signals.append('bearish_alignment')
        score += 25

    return {
        'score': score,
        'signals': signals,
        'ma20': round(ma20_val, 2),
        'ma60': round(ma60_val, 2),
        'ma120': round(ma120_val, 2),
    }


def check_macd_divergence(df: pd.DataFrame, window: int = 60) -> dict:
    """MACD 顶背离检测。

    EMA(12/26) → DIF, EMA(9) → DEA。
    60日窗口内价格高点上升但 DIF 高点下降 → 顶背离。
    """
    close = df['close'].values
    ema12 = _ema(pd.Series(close), 12).values
    ema26 = _ema(pd.Series(close), 26).values
    dif = ema12 - ema26
    dea = _ema(pd.Series(dif), 9).values

    signals = []
    score = 0

    n = len(df)
    if n < window:
        return {
            'score': 0, 'signals': [],
            'dif': round(float(dif[-1]), 4) if n > 26 else 0,
            'dea': round(float(dea[-1]), 4) if n > 26 else 0,
        }

    # Check last `window` days
    lookback = min(window, n - 26)
    if lookback < 20:
        return {
            'score': 0, 'signals': [],
            'dif': round(float(dif[-1]), 4),
            'dea': round(float(dea[-1]), 4),
        }

    start_idx = n - lookback

    # Find peaks in price and DIF within window
    price_peaks = []
    dif_peaks = []
    for i in range(start_idx + 2, n - 2):
        if close[i] > close[i - 1] and close[i] > close[i - 2] and close[i] > close[i + 1] and close[i] > close[i + 2]:
            price_peaks.append((i, close[i]))
        if not np.isnan(dif[i]) and dif[i] > dif[i - 1] and dif[i] > dif[i - 2] and dif[i] > dif[i + 1] and dif[i] > dif[i + 2]:
            dif_peaks.append((i, dif[i]))

    # Check divergence: last peak in price is higher but last peak in DIF is lower
    if len(price_peaks) >= 2 and len(dif_peaks) >= 2:
        last_price_peak = price_peaks[-1][1]
        prev_price_peak = price_peaks[-2][1]
        last_dif_peak = dif_peaks[-1][1]
        prev_dif_peak = dif_peaks[-2][1]
        if last_price_peak > prev_price_peak and last_dif_peak < prev_dif_peak:
            signals.append('macd_divergence')
            score = 15

    return {
        'score': score,
        'signals': signals,
        'dif': round(float(dif[-1]), 4),
        'dea': round(float(dea[-1]), 4),
    }


def check_volume_divergence(df: pd.DataFrame) -> dict:
    """量价背离检测。

    跌日平均成交量 > 涨日平均成交量 × 1.3 → 量价背离。
    """
    close = df['close'].values
    volume = df['volume'].values

    up_vols = []
    down_vols = []
    for i in range(1, len(df)):
        if close[i] > close[i - 1]:
            up_vols.append(volume[i])
        elif close[i] < close[i - 1]:
            down_vols.append(volume[i])

    up_avg = np.mean(up_vols) if up_vols else 0.0
    down_avg = np.mean(down_vols) if down_vols else 0.0
    ratio = down_avg / up_avg if up_avg > 0 else 0.0

    signals = []
    score = 0
    if ratio > 1.3:
        signals.append('volume_divergence')
        score = 15

    return {
        'score': score,
        'signals': signals,
        'ratio': round(float(ratio), 2),
    }


def _rsi(close: np.ndarray, period: int = 14) -> float:
    """Calculate RSI using Wilder's smoothing."""
    n = len(close)
    if n < period + 1:
        return 50.0
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # First average = SMA
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, n - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def check_momentum_rsi(df: pd.DataFrame) -> dict:
    """动量 + RSI 检测。

    Returns:
        {score, signals[], rsi}
    """
    close = df['close'].values
    low = df['low'].values

    signals = []
    score = 0

    # Lower lows: ≥3 of last 5 days
    lower_low_count = 0
    last_n = min(5, len(low) - 1)
    for i in range(len(low) - last_n, len(low) - 1):
        if low[i] < low[i - 1]:
            lower_low_count += 1
    if lower_low_count >= 3:
        signals.append('lower_lows')
        score += 10

    # RSI
    rsi_val = round(_rsi(close), 2)
    if rsi_val < 40:
        signals.append('rsi_weak')
        score += 10

    return {
        'score': score,
        'signals': signals,
        'rsi': rsi_val,
    }


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


# ═══════════════════════════════════════════════════════
# B-1: Bear Market Confirmation — 周度累计规则
# ═══════════════════════════════════════════════════════

BEAR_CONFIRM_DAYS = 3  # 过去5个交易日中 >N 天预警 → 熊市确认


def _check_bear_confirmation(history: list) -> bool:
    """检查是否触发熊市确认：过去5天 >3天 alert/danger"""
    if len(history) < 5:
        return False
    recent = history[-5:]
    alert_days = sum(1 for level in recent if level in ('alert', 'danger'))
    return alert_days > BEAR_CONFIRM_DAYS


def _get_recent_alert_history() -> list:
    """从DB读取最近5个交易日的预警等级"""
    import json
    try:
        from models import SessionLocal, MarketAlertLog
        db = SessionLocal()
        try:
            rows = db.query(MarketAlertLog)\
                     .order_by(MarketAlertLog.date.desc())\
                     .limit(5).all()
            return [r.level for r in reversed(rows)]
        finally:
            db.close()
    except Exception:
        return []


def _save_alert_log(date_str: str, level: str, score: int, signals: list):
    """保存预警日志到DB（UPSERT）"""
    import json
    from datetime import datetime as dt
    
    # 仅交易时段保存
    now = dt.now()
    h, m = now.hour, now.minute
    if not ((h == 9 and m >= 30) or h == 10 or (h == 11 and m <= 30) or
            h == 13 or h == 14 or (h == 15 and m == 0)):
        return
    
    try:
        from models import SessionLocal, MarketAlertLog
        db = SessionLocal()
        try:
            existing = db.query(MarketAlertLog).filter(
                MarketAlertLog.date == date_str
            ).first()
            signals_json = json.dumps(signals[:5], ensure_ascii=False)
            if existing:
                existing.level = level
                existing.score = score
                existing.signals = signals_json
            else:
                db.add(MarketAlertLog(
                    date=date_str, level=level, score=score,
                    signals=signals_json
                ))
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


# ═══════════════════════════════════════════════════════
# B0: Market Breadth — 硬性标准 (涨跌停家数)
# ═══════════════════════════════════════════════════════

LIMIT_DOWN_THRESHOLD = 50   # 跌停>50 → 恐慌信号
STRONG_STOCK_THRESHOLD = 50  # 涨幅>8% <50 → 市场弱


def _score_breadth(strong_count: int, limit_down: int) -> dict:
    """根据涨幅>8%家数和跌停家数计算风险分数（纯函数）"""
    score = 0
    signals = []
    
    if limit_down > LIMIT_DOWN_THRESHOLD:
        score += 15
        signals.append(f'跌停{limit_down}只(>{LIMIT_DOWN_THRESHOLD})，恐慌抛售信号')
    
    if strong_count < STRONG_STOCK_THRESHOLD:
        score += 15
        signals.append(f'涨幅>8%仅{strong_count}只(<{STRONG_STOCK_THRESHOLD})，市场做多意愿弱')
    
    return {
        'score': min(score, 25),
        'signals': signals,
        'strong_count': strong_count,
        'limit_down_count': limit_down,
    }


def check_market_breadth(date_str: str = None) -> dict:
    """获取今日涨幅>8%家数+跌停家数，计算市场宽度风险"""
    from datetime import datetime
    
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    
    try:
        import akshare as ak
        strong = ak.stock_zt_pool_strong_em(date=date_str)
        dt = ak.stock_zt_pool_dtgc_em(date=date_str)
        
        strong_count = len(strong[strong['涨跌幅'] > 8]) if '涨跌幅' in strong.columns else len(strong)
        limit_down = len(dt)
        
        result = _score_breadth(strong_count, limit_down)
        result['date'] = date_str
        return result
    except Exception as e:
        return {
            'score': 0,
            'signals': [f'涨跌停数据获取失败: {e}'],
            'strong_count': None,
            'limit_down_count': None,
            'date': date_str,
        }


def find_similar_patterns(df: pd.DataFrame, window: int = 20, top_k: int = 3) -> list:
    """查找相似历史形态。

    使用 20 日收益率的余弦相似度扫描历史窗口。
    """
    n = len(df)
    if n < window * 2 + 1:
        return []

    close = df['close'].values
    # Daily returns (percentage)
    returns = np.diff(close) / close[:-1]

    # Most recent window as query
    query = returns[-(window):]

    # Normalize query
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return []

    results = []
    # Scan all previous windows (at least window days before the end for future return)
    for i in range(len(returns) - window * 2, -1, -1):
        candidate = returns[i:i + window]
        sim = _cosine_similarity(query, candidate)

        # Future 20-day return after this window
        future_start = i + window
        future_end = min(future_start + window, n - 1)
        if future_end > future_start:
            future_ret = (close[future_end] - close[future_start]) / close[future_start]
        else:
            future_ret = 0.0

        direction = 'up' if future_ret > 0 else 'down'
        match_date = str(df['date'].iloc[i + window])[:10] if 'date' in df.columns else ''

        results.append({
            'similarity': round(sim, 4),
            'match_date': match_date,
            'future_20d_return': round(future_ret * 100, 2),
            'direction': direction,
        })

    # Sort by similarity descending, take top_k
    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:top_k]


def full_monitor(code: str = 'sh000001') -> dict:
    """综合大盘监控。

    Returns:
        {code, warning_level, total_score, verdict, suggest, signals,
         checks, similar_patterns, cur_price, timestamp}
    """
    from datetime import datetime

    try:
        df = get_index_kline(code)
    except Exception:
        df = pd.DataFrame()

    if df.empty or len(df) < 30:
        return {
            'code': code,
            'warning_level': 'normal',
            'total_score': 0,
            'verdict': '数据不足，无法评估',
            'suggest': '请确保有足够的历史数据',
            'signals': [],
            'checks': {},
            'similar_patterns': [],
            'cur_price': None,
            'timestamp': datetime.now().isoformat(),
        }

    # Run all checks
    breadth_check = check_market_breadth()
    adx_check = check_adx_trend(df)
    ma_check = check_ma_pattern(df)
    macd_check = check_macd_divergence(df)
    volume_check = check_volume_divergence(df)
    momentum_check = check_momentum_rsi(df)

    checks = {
        'breadth': breadth_check,
        'adx': adx_check,
        'ma': ma_check,
        'macd': macd_check,
        'volume': volume_check,
        'momentum_rsi': momentum_check,
    }

    # Aggregate signals and score
    all_signals = []
    total_score = 0
    for check in checks.values():
        total_score += check['score']
        all_signals.extend(check['signals'])

    # Warning level
    if total_score <= 20:
        warning_level = 'normal'
    elif total_score <= 40:
        warning_level = 'watch'
    elif total_score <= 60:
        warning_level = 'alert'
    else:
        warning_level = 'danger'

    # B-1: 保存日志 + 熊市确认检查
    from datetime import datetime as _dt
    today_str = _dt.now().strftime('%Y-%m-%d')
    _save_alert_log(today_str, warning_level, total_score, all_signals)

    history = _get_recent_alert_history()
    if _check_bear_confirmation(history):
        warning_level = 'danger'
        total_score = max(total_score, 85)
        alert_days = sum(1 for l in history[-5:] if l in ('alert', 'danger'))
        all_signals.append(
            f'⚠️ 熊市确认：近5日已有{alert_days}天预警，转入防御模式'
        )

    # Verdict and suggestion
    verdict_map = {
        'normal': '大盘处于正常状态',
        'watch': '大盘有走弱迹象，建议关注',
        'alert': '大盘风险较高，建议减仓观望',
        'danger': '大盘风险极高，建议清仓或对冲',
    }
    suggest_map = {
        'normal': '可正常操作，关注个股机会',
        'watch': '适当控制仓位，设置止盈止损',
        'alert': '降低仓位至50%以下，回避高位股',
        'danger': '清仓或使用对冲工具，等待企稳信号',
    }

    # Similar patterns
    similar = find_similar_patterns(df)

    cur_price = float(df['close'].iloc[-1])

    return {
        'code': code,
        'warning_level': warning_level,
        'total_score': total_score,
        'verdict': verdict_map.get(warning_level, ''),
        'suggest': suggest_map.get(warning_level, ''),
        'signals': all_signals,
        'checks': checks,
        'similar_patterns': similar,
        'cur_price': cur_price,
        'timestamp': datetime.now().isoformat(),
    }
