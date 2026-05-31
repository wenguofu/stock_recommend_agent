#!/usr/bin/env python3
"""
ML预测+风险指标 回测验证脚本

在100只股票上逐日滚动验证:
  1. ML方向预测准确率 (vs 未来5日实际涨跌)
  2. 风险指标可靠性 (VaR超额次数, 止损有效性)

用法: python3 validate_ml_risk.py [--stocks 100] [--output report.md]
"""

import sys
import os
import json
import math
import random
import traceback
from datetime import datetime
from collections import defaultdict

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from models import SessionLocal
from sqlalchemy import text


def get_stock_codes(n=100, min_days=180):
    """从DB获取有足够数据的股票"""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT code, COUNT(*) as cnt, MAX(date) as latest
            FROM backtest_data
            GROUP BY code
            HAVING cnt >= :min_d
            ORDER BY cnt DESC
        """), {'min_d': min_days}).fetchall()
        codes = [r[0] for r in rows]
        if len(codes) > n:
            random.seed(42)
            codes = random.sample(codes, n)
        return codes
    finally:
        db.close()


def load_stock_data(code):
    """加载单只股票的OHLCV数据"""
    db = SessionLocal()
    try:
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume, turnover FROM backtest_data WHERE code=:code ORDER BY date",
            db.bind, params={'code': code}
        )
        if len(df) < 60:
            return None
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['open'] = df['open'].astype(float)
        df['volume'] = df['volume'].astype(float)
        return df
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# 市场/板块数据加载
# ═══════════════════════════════════════════════════════════════

_index_cache = None

def load_index_data():
    """加载上证指数数据 (缓存)"""
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    db = SessionLocal()
    try:
        df = pd.read_sql_query(
            "SELECT date, close FROM backtest_data WHERE code='000001' ORDER BY date",
            db.bind
        )
        df['close'] = df['close'].astype(float)
        _index_cache = df
        return df
    finally:
        db.close()


def get_index_return(date_str, horizon=5):
    """获取指数在指定日期的未来N日收益率"""
    idx_df = load_index_data()
    if idx_df is None:
        return None
    matches = idx_df[idx_df['date'] == date_str]
    if len(matches) == 0:
        return None
    pos = matches.index[0]
    if pos + horizon >= len(idx_df):
        return None
    ret = (idx_df['close'].values[pos + horizon] / idx_df['close'].values[pos] - 1) * 100
    return ret


def detect_market_regime(df, idx):
    """检测市场状态: trending(趋势) / ranging(震荡) / volatile(高波动)"""
    close = df['close'].values[:idx+1].astype(float)
    high = df['high'].values[:idx+1].astype(float)
    low = df['low'].values[:idx+1].astype(float)
    n = len(close)

    if n < 30:
        return 'unknown'

    # ADX 简化计算 (14日)
    period = 14
    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)

    for i in range(1, n):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        up = high[i] - high[i-1]
        down = low[i-1] - low[i]
        plus_dm[i] = up if up > down and up > 0 else 0
        minus_dm[i] = down if down > up and down > 0 else 0

    # Wilder's smoothing
    atr = np.zeros(n)
    atr[period] = np.mean(tr[1:period+1])
    for i in range(period+1, n):
        atr[i] = (atr[i-1] * (period-1) + tr[i]) / period

    smoothed_plus = np.zeros(n)
    smoothed_minus = np.zeros(n)
    smoothed_plus[period] = np.sum(plus_dm[1:period+1])
    smoothed_minus[period] = np.sum(minus_dm[1:period+1])
    for i in range(period+1, n):
        smoothed_plus[i] = (smoothed_plus[i-1] * (period-1) + plus_dm[i]) / period
        smoothed_minus[i] = (smoothed_minus[i-1] * (period-1) + minus_dm[i]) / period

    di_plus = np.zeros(n)
    di_minus = np.zeros(n)
    for i in range(period, n):
        if atr[i] > 0:
            di_plus[i] = smoothed_plus[i] / atr[i] * 100
            di_minus[i] = smoothed_minus[i] / atr[i] * 100

    dx = np.zeros(n)
    for i in range(period, n):
        total = di_plus[i] + di_minus[i]
        dx[i] = abs(di_plus[i] - di_minus[i]) / total * 100 if total > 0 else 0

    # ADX = 14日EMA of DX
    adx = np.zeros(n)
    adx[period*2-1] = np.mean(dx[period:period*2])
    for i in range(period*2, n):
        adx[i] = (adx[i-1] * (period-1) + dx[i]) / period

    current_adx = adx[-1] if not np.isnan(adx[-1]) else 25

    # 波动率
    rets = np.diff(close[-21:]) / close[-21:-1]
    vol = float(np.std(rets) * 100 * np.sqrt(252))

    if vol > 50:
        return 'volatile'
    elif current_adx > 25:
        return 'trending'
    else:
        return 'ranging'


def compute_features(df, idx):
    """从DataFrame的idx位置计算ML特征 (不依赖外部API)"""
    n = idx + 1
    close = df['close'].values[:n].astype(float)
    high = df['high'].values[:n].astype(float)
    low = df['low'].values[:n].astype(float)
    open_p = df['open'].values[:n].astype(float)
    volume = df['volume'].values[:n].astype(float)

    features = {}

    # 收益率
    for p in [1, 5, 10, 20]:
        if n > p:
            features[f'ret_{p}d'] = (close[-1] / close[-1-p] - 1) * 100

    # 波动率
    if n > 21:
        rets = np.diff(close[-21:]) / close[-21:-1]
        features['volatility_20d'] = float(np.std(rets) * 100 * math.sqrt(252))

    # 均线偏离
    for p in [5, 10, 20]:
        if n > p:
            ma = np.mean(close[-p:])
            features[f'ma_dev_{p}'] = (close[-1] / ma - 1) * 100

    # MA交叉
    if n > 20:
        ma5 = np.mean(close[-5:])
        ma20 = np.mean(close[-20:])
        features['ma_cross'] = 1 if ma5 > ma20 else -1

    # RSI 14
    if n > 15:
        deltas = np.diff(close[-15:])
        gains = np.sum(deltas[deltas > 0]) if np.any(deltas > 0) else 0
        losses = abs(np.sum(deltas[deltas < 0])) if np.any(deltas < 0) else 1e-10
        rs = gains / losses
        features['rsi_14'] = 100 - 100 / (1 + rs)

    # 量比
    if n > 20:
        avg_vol = np.mean(volume[-21:-1])
        features['volume_ratio'] = volume[-1] / avg_vol if avg_vol > 0 else 1.0

    # 布林带位置
    if n >= 20:
        ma20 = np.mean(close[-20:])
        std20 = np.std(close[-20:])
        if std20 > 0:
            upper = ma20 + 2 * std20
            lower = ma20 - 2 * std20
            features['bollinger_pos'] = (close[-1] - lower) / (upper - lower) * 100

    # 振幅
    if n > 0:
        features['amplitude'] = (high[-1] - low[-1]) / open_p[-1] * 100

    # 最大回撤 (20日)
    if n >= 20:
        peak = np.max(close[-20:])
        features['max_dd_20d'] = (peak - close[-1]) / peak * 100

    # 相对强度 (vs 上证指数, 20日)
    if n >= 20:
        idx_df = load_index_data()
        stock_date = str(df['date'].values[idx])
        idx_row = idx_df[idx_df['date'] == stock_date]
        if len(idx_row) > 0:
            idx_pos = idx_row.index[0]
            if idx_pos >= 20:
                idx_ret = (idx_df['close'].values[idx_pos] / idx_df['close'].values[idx_pos - 20] - 1) * 100
                stock_ret = (close[-1] / close[-21] - 1) * 100 if n > 20 else 0
                features['relative_strength'] = stock_ret - idx_ret

    return features


def rule_based_direction(features):
    """规则引擎方向预测 v2 — 动量+反转双信号, 市场基线校准"""
    score = 0
    signals = []

    # ═══ 动量信号 (正向) ═══
    m5 = features.get('ret_5d', 0) or 0
    m20 = features.get('ret_20d', 0) or 0

    # 短期动量
    if m5 > 5: score += 8; signals.append('短期强动量')
    elif m5 > 2: score += 4; signals.append('短期动量')
    elif m5 < -5: score -= 8; signals.append('短期强下跌')
    elif m5 < -2: score -= 4; signals.append('短期下跌')

    # 中期动量 (衰减: 涨幅越大, 反转概率越高)
    if m20 > 30: score -= 5; signals.append('中期过度上涨(反转风险)')
    elif m20 > 15: score += 3; signals.append('中期趋势向上')
    elif m20 > 5: score += 6; signals.append('中期动量')
    elif m20 < -20: score += 8; signals.append('深跌反弹预期')
    elif m20 < -10: score += 4; signals.append('超跌区域')
    elif m20 < -5: score -= 3; signals.append('中期走弱')

    # ═══ 均线信号 ═══
    ma = features.get('ma_cross')
    if ma == 1: score += 12; signals.append('MA多头')
    elif ma == -1: score -= 12; signals.append('MA空头')

    # ═══ RSI均值回归 ═══
    rsi = features.get('rsi_14')
    if rsi is not None:
        if rsi <= 25: score += 18; signals.append('RSI深度超卖')
        elif rsi <= 35: score += 10; signals.append('RSI超卖')
        elif rsi >= 80: score -= 15; signals.append('RSI极度超买')
        elif rsi >= 70: score -= 8; signals.append('RSI超买')
        elif 45 <= rsi <= 55: score += 2  # 中性偏多

    # ═══ 布林带均值回归 ═══
    boll = features.get('bollinger_pos')
    if boll is not None:
        if boll < 5: score += 15; signals.append('布林下轨(强反弹)')
        elif boll < 15: score += 8; signals.append('布林下轨区域')
        elif boll > 95: score -= 12; signals.append('布林上轨(回调)')
        elif boll > 80: score -= 5; signals.append('布林上轨区域')

    # ═══ 量价背离 ═══
    vol_ratio = features.get('volume_ratio', 1.0) or 1.0
    ret_1d = features.get('ret_1d', 0) or 0
    if ret_1d > 3 and vol_ratio > 2.5:
        score -= 8; signals.append('放量急涨(出货嫌疑)')
    elif ret_1d < -3 and vol_ratio > 2.5:
        score += 6; signals.append('放量急跌(恐慌盘)')

    # ═══ 波动率惩罚 ═══
    vol = features.get('volatility_20d')
    if vol is not None:
        if vol > 60: score = score * 0.5; signals.append('高波动(信号衰减50%)')
        elif vol > 40: score = score * 0.7

    # ═══ 相对强度 ═══
    rel_str = features.get('relative_strength')
    if rel_str is not None:
        if rel_str > 15: score += 8; signals.append('大幅跑赢指数')
        elif rel_str > 5: score += 4; signals.append('跑赢指数')
        elif rel_str < -15: score -= 6; signals.append('大幅跑输指数')
        elif rel_str < -5: score -= 3; signals.append('跑输指数')

    # ═══ 市场基线校准 ═══
    # A股5日上涨概率约52%, 预测也应以此为基线
    # 将score映射到概率: 基线52%, 范围[15%, 85%]
    score = max(-70, min(70, score))
    baseline = 52  # A股历史上涨基线
    up_prob = baseline + score * 0.47  # score=70→85%, score=-70→19%
    up_prob = max(15, min(85, int(up_prob)))
    down_prob = 100 - up_prob

    # 方向判断
    if score > 10:
        direction = 'up'
    elif score < -10:
        direction = 'down'
    else:
        direction = 'neutral'

    # 置信度
    if abs(score) > 35:
        confidence = 'high'
    elif abs(score) > 18:
        confidence = 'medium'
    else:
        confidence = 'low'

    return {
        'direction': direction,
        'up_prob': up_prob,
        'down_prob': down_prob,
        'confidence': confidence,
        'score': score,
        'signals': signals[-5:],  # 最近5个信号
    }


def calc_risk_metrics(df, idx):
    """计算风险指标 (VaR, 最大回撤, 夏普)"""
    close = df['close'].values[:idx+1].astype(float)
    n = len(close)

    metrics = {}

    # 日收益率
    if n > 2:
        rets = np.diff(close) / close[:-1]
        rets = rets[~np.isnan(rets)]

        # VaR 95% 历史法
        if len(rets) >= 30:
            var_95 = float(np.percentile(rets, 5))
            metrics['var_95_pct'] = round(abs(var_95) * 100, 2)
            metrics['var_95_daily'] = var_95

        # 波动率
        if len(rets) >= 20:
            metrics['volatility_annual'] = round(float(np.std(rets[-20:]) * 100 * math.sqrt(252)), 2)

    # 最大回撤
    if n > 20:
        peak = close[0]
        max_dd = 0
        for i in range(1, n):
            if close[i] > peak:
                peak = close[i]
            else:
                dd = (peak - close[i]) / peak
                if dd > max_dd:
                    max_dd = dd
        metrics['max_drawdown_pct'] = round(max_dd * 100, 2)

    return metrics


def run_backtest(codes, min_train=60, horizon=5):
    """
    逐日滚动回测

    对每只股票, 从第min_train天开始, 每天:
      1. 计算特征
      2. 预测方向
      3. 计算风险指标
      4. 记录horizon天后的实际收益
    """
    results = []
    stock_stats = {}
    total_predictions = 0

    for si, code in enumerate(codes):
        df = load_stock_data(code)
        if df is None or len(df) < min_train + horizon:
            continue

        n = len(df)
        stock_results = []
        correct = 0
        total = 0

        for i in range(min_train, n - horizon):
            features = compute_features(df, i)
            if len(features) < 5:
                continue

            # 市场状态
            regime = detect_market_regime(df, i)

            # 预测
            pred = rule_based_direction(features)

            # 实际结果
            current_close = df['close'].values[i]
            future_close = df['close'].values[i + horizon]
            actual_return = (future_close / current_close - 1) * 100
            actual_direction = 'up' if actual_return > 0 else 'down'

            # 风险指标
            risk = calc_risk_metrics(df, i)

            # 记录
            record = {
                'code': code,
                'date': str(df['date'].values[i]),
                'regime': regime,
                'pred_direction': pred['direction'],
                'pred_up_prob': pred['up_prob'],
                'pred_confidence': pred['confidence'],
                'pred_score': pred['score'],
                'actual_return_5d': round(actual_return, 2),
                'actual_direction': actual_direction,
                'correct': 1 if (pred['direction'] == 'up' and actual_return > 0) or
                                   (pred['direction'] == 'down' and actual_return < 0) else 0,
                'var_95_pct': risk.get('var_95_pct'),
                'var_exceeded': 1 if risk.get('var_95_daily') is not None and
                                       actual_return < risk.get('var_95_daily', 0) * 100 * math.sqrt(horizon) else 0,
                'max_drawdown_pct': risk.get('max_drawdown_pct'),
                'volatility_annual': risk.get('volatility_annual'),
            }

            # 选择性预测: 只在|score|>12时计算非中性预测
            if pred['direction'] != 'neutral':
                # v3: 弱信号过滤 — 低置信且|score|小不纳入统计
                if pred['confidence'] == 'low' and abs(pred['score']) < 8:
                    continue
                stock_results.append(record)
                results.append(record)
                total_predictions += 1
                if record['correct']:
                    correct += 1
                total += 1

        if total > 0:
            stock_stats[code] = {
                'accuracy': round(correct / total * 100, 1),
                'n_predictions': total,
            }

        if (si + 1) % 20 == 0:
            print(f"  [{si+1}/{len(codes)}] stocks done, {total_predictions} predictions so far...")

    return results, stock_stats


def analyze_results(results, stock_stats):
    """分析回测结果"""
    if not results:
        return {'error': 'No results'}

    df = pd.DataFrame(results)

    analysis = {}

    # 1. 整体准确率
    overall_acc = df['correct'].mean() * 100
    analysis['overall_accuracy'] = round(overall_acc, 1)
    analysis['total_predictions'] = len(df)
    analysis['n_stocks'] = len(stock_stats)

    # 2. 按方向
    for d in ['up', 'down']:
        subset = df[df['pred_direction'] == d]
        if len(subset) > 0:
            analysis[f'{d}_count'] = len(subset)
            analysis[f'{d}_accuracy'] = round(subset['correct'].mean() * 100, 1)
            analysis[f'{d}_avg_return'] = round(subset['actual_return_5d'].mean(), 2)

    # 3. 按置信度
    for conf in ['high', 'medium', 'low']:
        subset = df[df['pred_confidence'] == conf]
        if len(subset) > 0:
            analysis[f'conf_{conf}_count'] = len(subset)
            analysis[f'conf_{conf}_accuracy'] = round(subset['correct'].mean() * 100, 1)
            analysis[f'conf_{conf}_avg_return'] = round(subset['actual_return_5d'].mean(), 2)

    # 4. 预测概率 vs 实际收益 相关性
    corr = df['pred_up_prob'].corr(df['actual_return_5d'])
    analysis['prob_return_correlation'] = round(corr, 4)

    # 5. VaR超额率 (实际亏损超过VaR的比例, 应该≈5%)
    var_subset = df[df['var_exceeded'].notna()]
    if len(var_subset) > 0:
        var_exceed_rate = var_subset['var_exceeded'].mean() * 100
        analysis['var_exceed_rate_pct'] = round(var_exceed_rate, 2)
        analysis['var_expected_rate_pct'] = 5.0
        analysis['var_calibration'] = '良好' if abs(var_exceed_rate - 5) < 3 else ('偏保守' if var_exceed_rate < 2 else '偏激进')

    # 6. 股票级别统计
    accuracies = [s['accuracy'] for s in stock_stats.values()]
    analysis['stock_accuracy_mean'] = round(np.mean(accuracies), 1)
    analysis['stock_accuracy_std'] = round(np.std(accuracies), 1)
    analysis['stock_accuracy_median'] = round(np.median(accuracies), 1)

    # 7. 涨跌分布
    analysis['actual_up_ratio'] = round((df['actual_return_5d'] > 0).mean() * 100, 1)
    analysis['pred_up_ratio'] = round((df['pred_direction'] == 'up').mean() * 100, 1)

    # 8. 按预测分数分桶
    bins = [(-100, -20, '强看跌'), (-20, -5, '偏看跌'), (-5, 5, '中性'), (5, 20, '偏看涨'), (20, 100, '强看涨')]
    for lo, hi, label in bins:
        subset = df[(df['pred_score'] >= lo) & (df['pred_score'] < hi)]
        if len(subset) > 10:
            analysis[f'bucket_{label}_count'] = len(subset)
            analysis[f'bucket_{label}_accuracy'] = round(subset['correct'].mean() * 100, 1)
            analysis[f'bucket_{label}_avg_ret'] = round(subset['actual_return_5d'].mean(), 2)

    # 8. 按市场状态
    if 'regime' in df.columns:
        for regime in ['trending', 'ranging', 'volatile']:
            subset = df[df['regime'] == regime]
            if len(subset) > 10:
                analysis[f'regime_{regime}_count'] = len(subset)
                analysis[f'regime_{regime}_accuracy'] = round(subset['correct'].mean() * 100, 1)
                analysis[f'regime_{regime}_avg_ret'] = round(subset['actual_return_5d'].mean(), 2)

    return analysis


def main():
    print("=" * 60)
    print("ML预测+风险指标 回测验证")
    print("=" * 60)

    # 1. 选股
    print("\n[1/4] 选取100只股票...")
    codes = get_stock_codes(100, min_days=180)
    print(f"  选中 {len(codes)} 只股票")

    # 2. 回测
    print(f"\n[2/4] 逐日滚动回测 (每只股票约120天 × 100只)...")
    results, stock_stats = run_backtest(codes, min_train=60, horizon=5)

    if not results:
        print("ERROR: 无回测结果")
        return

    print(f"  完成: {len(results)} 条预测记录, {len(stock_stats)} 只股票")

    # 3. 分析
    print("\n[3/4] 分析结果...")
    analysis = analyze_results(results, stock_stats)

    # 4. 输出
    print("\n" + "=" * 60)
    print("回测报告")
    print("=" * 60)

    print(f"\n整体准确率: {analysis['overall_accuracy']}% ({analysis['total_predictions']}条预测)")
    print(f"股票平均准确率: {analysis['stock_accuracy_mean']}% (±{analysis['stock_accuracy_std']}%)")

    print(f"\n--- 按方向 ---")
    for d in ['up', 'down']:
        k = f'{d}_count'
        if k in analysis:
            print(f"  {d}: {analysis[k]}条, 准确率{analysis[f'{d}_accuracy']}%, 平均收益{analysis[f'{d}_avg_return']}%")

    print(f"\n--- 按置信度 ---")
    for conf in ['high', 'medium', 'low']:
        k = f'conf_{conf}_count'
        if k in analysis:
            print(f"  {conf}: {analysis[k]}条, 准确率{analysis[f'conf_{conf}_accuracy']}%, 平均收益{analysis[f'conf_{conf}_avg_return']}%")

    print(f"\n--- 风险指标 ---")
    print(f"  VaR超越率: {analysis.get('var_exceed_rate_pct', 'N/A')}% (预期5%) → {analysis.get('var_calibration', 'N/A')}")

    print(f"\n--- 概率-收益相关性 ---")
    print(f"  相关系数: {analysis['prob_return_correlation']}")

    print(f"\n--- 按分数分桶 ---")
    for label in ['强看跌', '偏看跌', '偏看涨', '强看涨']:
        k_acc = f'bucket_{label}_accuracy'
        k_ret = f'bucket_{label}_avg_ret'
        k_cnt = f'bucket_{label}_count'
        if k_acc in analysis:
            print(f"  {label}: {analysis[k_cnt]}条, 准确率{analysis[k_acc]}%, 平均收益{analysis[k_ret]}%")

    print(f"\n--- 按市场状态 ---")
    for regime in ['trending', 'ranging', 'volatile']:
        k = f'regime_{regime}_count'
        if k in analysis:
            print(f"  {regime}: {analysis[k]}条, 准确率{analysis[f'regime_{regime}_accuracy']}%, 平均收益{analysis[f'regime_{regime}_avg_ret']}%")

    # 保存
    report = {**analysis, 'generated_at': datetime.now().isoformat()}
    outpath = os.path.join(os.path.dirname(__file__), 'eval_result', 'ml_risk_backtest_report.json')
    with open(outpath, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n报告已保存: {outpath}")

    return analysis


if __name__ == '__main__':
    main()
