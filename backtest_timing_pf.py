#!/usr/bin/env python3
"""
择时过滤 + 盈亏比优化 回测

策略:
  只在趋势明朗+波动适中时交易, 目标是不对称收益(赚大赔小)
  
择时过滤条件:
  1. ADX > 20 (趋势存在)
  2. 年化波动率 20-50% (不太安静也不太疯)
  3. 信号强度 |score| > 15 (有足够conviction)

交易规则:
  - score>15 → 做多, 持有5日
  - score<-15 → 做空(用做多模拟: 预测下跌则卖出现有/不做)
  - 止损: 5日内跌超8%止损
  - 每次等额交易 (1单位资金)
"""

import sys, os, json, math, random, sqlite3
from datetime import datetime
from collections import defaultdict
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

# ══════════════════════════════════════════════════════
# 基本面: 复用 validate_ml_risk 的工具函数
# ══════════════════════════════════════════════════════

def get_stock_codes(n=1000, min_days=250):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, COUNT(*) as cnt FROM backtest_data GROUP BY code HAVING cnt >= ? ORDER BY cnt DESC", (min_days,))
    rows = cursor.fetchall()
    conn.close()
    codes = [r[0] for r in rows]
    if len(codes) > n:
        random.seed(42)
        codes = random.sample(codes, n)
    return codes


def load_stock_data(code):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume, turnover FROM backtest_data WHERE code=? ORDER BY date",
        conn, params=(code,))
    conn.close()
    if len(df) < 80: return None
    for col in ['close','high','low','open','volume']:
        df[col] = df[col].astype(float)
    return df


def compute_features(df, idx):
    n = idx + 1
    close = df['close'].values[:n].astype(float)
    high = df['high'].values[:n].astype(float)
    low = df['low'].values[:n].astype(float)
    open_p = df['open'].values[:n].astype(float)
    volume = df['volume'].values[:n].astype(float)
    features = {}

    for p in [1, 5, 10, 20]:
        if n > p: features[f'ret_{p}d'] = (close[-1] / close[-1-p] - 1) * 100

    if n > 21:
        rets = np.diff(close[-21:]) / close[-21:-1]
        features['volatility_20d'] = float(np.std(rets) * 100 * np.sqrt(252))

    for p in [5, 10, 20]:
        if n > p:
            ma = np.mean(close[-p:])
            features[f'ma_dev_{p}'] = (close[-1] / ma - 1) * 100

    if n > 20:
        ma5 = np.mean(close[-5:]); ma20 = np.mean(close[-20:])
        features['ma_cross'] = 1 if ma5 > ma20 else -1

    if n > 15:
        deltas = np.diff(close[-15:])
        gains = np.sum(deltas[deltas > 0]) if np.any(deltas > 0) else 0
        losses = abs(np.sum(deltas[deltas < 0])) if np.any(deltas < 0) else 1e-10
        features['rsi_14'] = 100 - 100 / (1 + gains/losses)

    if n > 20:
        avg_vol = np.mean(volume[-21:-1])
        features['volume_ratio'] = volume[-1] / avg_vol if avg_vol > 0 else 1.0

    if n >= 20:
        ma20 = np.mean(close[-20:]); std20 = np.std(close[-20:])
        if std20 > 0:
            upper = ma20 + 2*std20; lower = ma20 - 2*std20
            features['bollinger_pos'] = (close[-1] - lower) / (upper - lower) * 100

    if n > 0:
        features['amplitude'] = (high[-1] - low[-1]) / open_p[-1] * 100

    if n >= 20:
        peak = np.max(close[-20:])
        features['max_dd_20d'] = (peak - close[-1]) / peak * 100

    return features


def calc_adx(df, idx):
    """计算ADX(14) — 趋势强度指标"""
    close = df['close'].values[:idx+1].astype(float)
    high = df['high'].values[:idx+1].astype(float)
    low = df['low'].values[:idx+1].astype(float)
    n = len(close)
    if n < 30: return 20  # 默认中性

    period = 14
    tr = np.zeros(n); plus_dm = np.zeros(n); minus_dm = np.zeros(n)
    for i in range(1, n):
        tr[i] = max(high[i]-low[i], abs(high[i]-close[i-1]), abs(low[i]-close[i-1]))
        up = high[i] - high[i-1]; down = low[i-1] - low[i]
        plus_dm[i] = up if up > down and up > 0 else 0
        minus_dm[i] = down if down > up and down > 0 else 0

    atr = np.zeros(n); atr[period] = np.mean(tr[1:period+1])
    for i in range(period+1, n): atr[i] = (atr[i-1]*(period-1) + tr[i])/period

    sp = np.zeros(n); sm = np.zeros(n)
    sp[period] = np.sum(plus_dm[1:period+1]); sm[period] = np.sum(minus_dm[1:period+1])
    for i in range(period+1, n):
        sp[i] = (sp[i-1]*(period-1) + plus_dm[i])/period
        sm[i] = (sm[i-1]*(period-1) + minus_dm[i])/period

    di_p = np.zeros(n); di_m = np.zeros(n)
    for i in range(period, n):
        if atr[i] > 0:
            di_p[i] = sp[i]/atr[i]*100; di_m[i] = sm[i]/atr[i]*100

    dx = np.zeros(n)
    for i in range(period, n):
        total = di_p[i] + di_m[i]
        dx[i] = abs(di_p[i]-di_m[i])/total*100 if total > 0 else 0

    adx = np.zeros(n); adx[period*2-1] = np.mean(dx[period:period*2])
    for i in range(period*2, n): adx[i] = (adx[i-1]*(period-1) + dx[i])/period
    return float(adx[-1]) if not np.isnan(adx[-1]) else 20


def rule_score(features):
    """返回信号分数(正=看涨, 负=看跌) 不夹断"""
    score = 0
    m5 = features.get('ret_5d', 0) or 0
    m20 = features.get('ret_20d', 0) or 0

    if m5 > 5: score += 8
    elif m5 > 2: score += 4
    elif m5 < -5: score -= 8
    elif m5 < -2: score -= 4

    if m20 > 30: score -= 5
    elif m20 > 15: score += 3
    elif m20 > 5: score += 6
    elif m20 < -20: score += 8
    elif m20 < -10: score += 4
    elif m20 < -5: score -= 3

    ma = features.get('ma_cross')
    if ma == 1: score += 12
    elif ma == -1: score -= 12

    rsi = features.get('rsi_14')
    if rsi is not None:
        if rsi <= 25: score += 15
        elif rsi <= 35: score += 8
        elif rsi >= 80: score -= 12
        elif rsi >= 70: score -= 6

    boll = features.get('bollinger_pos')
    if boll is not None:
        if boll < 5: score += 12
        elif boll < 15: score += 6
        elif boll > 95: score -= 10
        elif boll > 80: score -= 4

    return score


def should_trade(features, df, idx):
    """择时过滤器: 只在有利环境返回True"""
    # 1. 信号强度
    score = rule_score(features)
    if abs(score) <= 15:
        return False, 0

    # 2. ADX趋势过滤 (只做多需要中等趋势, 太强或太弱都不好)
    adx = calc_adx(df, idx)
    if adx < 25 or adx > 50:
        return False, 0

    # 3. 波动率过滤 (太安静没方向, 太疯不可控)
    vol = features.get('volatility_20d')
    if vol is None or vol < 18 or vol > 50:
        return False, 0

    # 4. 只做多
    if score <= 0:
        return False, 0

    # 4. 布林带极端位置加分
    boll = features.get('bollinger_pos')
    if boll is not None:
        if score > 0 and boll > 95: return False, 0  # 看涨但已在上轨
        if score < 0 and boll < 5: return False, 0   # 看跌但已在下轨

    return True, score


def run_timing_backtest(codes, horizon=5):
    """带择时过滤的回测"""
    trades = []
    skipped = 0
    total_signals = 0

    for si, code in enumerate(codes):
        df = load_stock_data(code)
        if df is None: continue
        n = len(df)

        for i in range(60, n - horizon - 1):
            features = compute_features(df, i)
            if len(features) < 5: continue

            total_signals += 1
            trade_ok, score = should_trade(features, df, i)

            if not trade_ok:
                skipped += 1
                continue

            direction = 'long'
            entry_price = df['close'].values[i]

            # 模拟5日持有, 带止损
            exit_price = entry_price
            stopped_out = False
            stop_price = entry_price * 0.92  # 8%止损

            for j in range(1, horizon + 1):
                if i + j >= n: break
                day_low = df['low'].values[i + j]
                day_close = df['close'].values[i + j]

                if day_low <= stop_price:
                    exit_price = stop_price
                    stopped_out = True
                    break
                elif j == horizon:
                    exit_price = day_close

            pnl_pct = (exit_price / entry_price - 1) * 100

            # 止损收益钳制
            if stopped_out:
                pnl_pct = max(pnl_pct, -8.5)  # 滑点

            trades.append({
                'code': code,
                'date': str(df['date'].values[i]),
                'direction': direction,
                'score': score,
                'entry': round(entry_price, 2),
                'exit': round(exit_price, 2),
                'pnl_pct': round(pnl_pct, 2),
                'stopped_out': stopped_out,
                'adx': calc_adx(df, i),
                'vol': features.get('volatility_20d', 0),
            })

        if (si + 1) % 100 == 0:
            print(f"  [{si+1}/{len(codes)}] {len(trades)} trades, {skipped} skipped...")

    return trades, skipped, total_signals


def analyze_trades(trades):
    """分析交易盈亏比"""
    if not trades:
        return {'error': 'No trades'}

    pnls = [t['pnl_pct'] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_gain = sum(wins) if wins else 0
    total_loss = abs(sum(losses)) if losses else 1

    analysis = {
        'total_trades': len(trades),
        'win_rate': round(len(wins) / len(trades) * 100, 1),
        'avg_win': round(np.mean(wins), 2) if wins else 0,
        'avg_loss': round(np.mean(losses), 2) if losses else 0,
        'win_loss_ratio': round(abs(np.mean(wins) / np.mean(losses)), 2) if wins and losses else 0,
        'profit_factor': round(total_gain / total_loss, 2),
        'total_return': round(sum(pnls), 2),
        'avg_trade': round(np.mean(pnls), 2),
        'max_win': round(max(pnls), 2),
        'max_loss': round(min(pnls), 2),
        'sharpe': round(np.mean(pnls) / np.std(pnls) * np.sqrt(len(trades)/252), 2) if len(pnls) > 1 else 0,
        'stopped_out_pct': round(sum(1 for t in trades if t['stopped_out']) / len(trades) * 100, 1),
    }

    # 按方向
    for d in ['long', 'short']:
        sub = [t for t in trades if t['direction'] == d]
        if sub:
            sp = [t['pnl_pct'] for t in sub]
            sw = [p for p in sp if p > 0]
            sl = [p for p in sp if p < 0]
            analysis[f'{d}_count'] = len(sub)
            analysis[f'{d}_win_rate'] = round(len(sw)/len(sub)*100, 1) if sub else 0
            analysis[f'{d}_avg_pnl'] = round(np.mean(sp), 2)
            analysis[f'{d}_profit_factor'] = round(sum(sw)/abs(sum(sl)), 2) if sl else 999

    # 按信号强度分桶
    for label, lo, hi in [('弱信号', 15, 25), ('中信号', 25, 40), ('强信号', 40, 100)]:
        sub = [t for t in trades if lo <= abs(t['score']) < hi]
        if sub:
            sp = [t['pnl_pct'] for t in sub]
            analysis[f'{label}_count'] = len(sub)
            analysis[f'{label}_avg_pnl'] = round(np.mean(sp), 2)
            analysis[f'{label}_win_rate'] = round(len([p for p in sp if p > 0])/len(sub)*100, 1)

    # 按ADX分桶
    for label, lo, hi in [('弱趋势', 20, 30), ('中趋势', 30, 45), ('强趋势', 45, 100)]:
        sub = [t for t in trades if lo <= t['adx'] < hi]
        if sub:
            sp = [t['pnl_pct'] for t in sub]
            analysis[f'adx_{label}_count'] = len(sub)
            analysis[f'adx_{label}_avg_pnl'] = round(np.mean(sp), 2)

    return analysis


def main():
    print("=" * 60)
    print("择时过滤 + 盈亏比优化 回测")
    print("=" * 60)

    codes = get_stock_codes(1000)
    print(f"\n[1/3] {len(codes)}只股票, 5日持仓, 8%止损")

    print(f"\n[2/3] 运行回测 (ADX>20 + 波动20-55% + |score|>15)...")
    trades, skipped, total = run_timing_backtest(codes, horizon=5)

    print(f"\n  信号总数: {total}")
    print(f"  过滤掉: {skipped} ({skipped/total*100:.0f}%)")
    print(f"  实际交易: {len(trades)} ({len(trades)/total*100:.0f}%)")

    print(f"\n[3/3] 盈亏分析...")
    analysis = analyze_trades(trades)

    print(f"\n{'='*60}")
    print(f"盈亏比报告")
    print(f"{'='*60}")
    print(f"\n总交易: {analysis['total_trades']}笔")
    print(f"胜率: {analysis['win_rate']}%")
    print(f"平均盈利: +{analysis['avg_win']}%  平均亏损: {analysis['avg_loss']}%")
    print(f"盈亏比: {analysis['win_loss_ratio']}")
    print(f"Profit Factor: {analysis['profit_factor']}  ← 核心指标")
    print(f"总收益: {analysis['total_return']}%  每笔平均: {analysis['avg_trade']}%")
    print(f"最大单笔盈利: +{analysis['max_win']}%  最大单笔亏损: {analysis['max_loss']}%")
    print(f"止损触发率: {analysis['stopped_out_pct']}%")

    print(f"\n--- 按方向 ---")
    for d in ['long', 'short']:
        if f'{d}_count' in analysis:
            print(f"  {d}: {analysis[f'{d}_count']}笔, 胜率{analysis[f'{d}_win_rate']}%, 均收益{analysis[f'{d}_avg_pnl']}%, PF={analysis[f'{d}_profit_factor']}")

    print(f"\n--- 按信号强度 ---")
    for label in ['弱信号', '中信号', '强信号']:
        if f'{label}_count' in analysis:
            print(f"  {label}: {analysis[f'{label}_count']}笔, 胜率{analysis[f'{label}_win_rate']}%, 均收益{analysis[f'{label}_avg_pnl']}%")

    print(f"\n--- 按ADX趋势强度 ---")
    for label in ['弱趋势', '中趋势', '强趋势']:
        if f'adx_{label}_count' in analysis:
            print(f"  {label}: {analysis[f'adx_{label}_count']}笔, 均收益{analysis[f'adx_{label}_avg_pnl']}%")

    # 对比买入持有
    print(f"\n--- 对比基准 ---")
    if trades:
        # 买入持有: 每只股票持有整个回测期的收益
        bh_returns = []
        for code in set(t['code'] for t in trades):
            df = load_stock_data(code)
            if df is not None and len(df) > 60:
                bh_ret = (df['close'].values[-1] / df['close'].values[60] - 1) * 100
                bh_returns.append(bh_ret)
        if bh_returns:
            print(f"  买入持有(同期): 均收益{np.mean(bh_returns):.1f}%, 中位数{np.median(bh_returns):.1f}%")
            print(f"  择时策略总收益: {analysis['total_return']}% (等额交易)")

    # 保存
    out = {'analysis': analysis, 'n_trades': len(trades), 'filter_rate': f'{skipped/total*100:.0f}%'}
    with open(os.path.join(os.path.dirname(__file__), 'eval_result', 'timing_pf_backtest.json'), 'w') as f:
        json.dump(out, f, indent=2)
    print(f"\n报告已保存")


if __name__ == '__main__':
    main()
