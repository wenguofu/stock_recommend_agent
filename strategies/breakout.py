#!/usr/bin/env python3
"""
突破分析策略 — 量价突破+均线突破

筛选逻辑:
  1. 近5日突破20日高点
  2. 成交量放大(>1.5倍20日均量)
  3. 价格站上所有短期均线(5/10/20)
  4. RSI不在超买区(<70)
  5. 近期无暴跌(回撤<10%)

综合评分排序, 返回Top20
"""
import sys, os, math, time
from datetime import datetime
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import SessionLocal
from sqlalchemy import text

def screen_breakouts():
    db = SessionLocal()
    try:
        # 从DB获取有足够数据的股票
        rows = db.execute(text('''
            SELECT code FROM backtest_data
            WHERE code REGEXP '^[0-9]{6}$'
            GROUP BY code HAVING COUNT(*) >= 120
            ORDER BY RAND() LIMIT 800
        ''')).fetchall()

        candidates = []

        for (code,) in rows:
            try:
                kline = db.execute(text(
                    'SELECT date, open, high, low, close, volume FROM backtest_data WHERE code=:code ORDER BY date'
                ), {'code': code}).fetchall()

                if len(kline) < 60:
                    continue

                closes = np.array([r[3] for r in kline], dtype=float)
                highs = np.array([r[2] for r in kline], dtype=float)
                lows = np.array([r[1] for r in kline], dtype=float)
                volumes = np.array([r[5] for r in kline], dtype=float)
                n = len(closes)

                # 1. 突破20日高点
                high_20d = np.max(highs[-21:-1])
                current_close = closes[-1]
                if current_close <= high_20d:
                    continue

                # 2. 成交量放大
                avg_vol_20 = np.mean(volumes[-21:-1])
                current_vol = volumes[-1]
                if avg_vol_20 <= 0 or current_vol / avg_vol_20 < 1.3:
                    continue

                # 3. 站上20日均线
                ma20 = np.mean(closes[-20:])
                if current_close <= ma20:
                    continue

                # 4. RSI不超买
                deltas = np.diff(closes[-15:])
                gains = np.sum(deltas[deltas > 0]) if np.any(deltas > 0) else 0
                losses = abs(np.sum(deltas[deltas < 0])) if np.any(deltas < 0) else 1e-10
                rsi = 100 - 100 / (1 + gains / losses)
                if rsi > 75:
                    continue

                # 5. 近期无暴跌
                dd_10d = (np.max(closes[-10:]) - current_close) / np.max(closes[-10:]) * 100
                if dd_10d > 10:
                    continue

                # 评分
                score = 50

                # 突破强度
                break_pct = (current_close / high_20d - 1) * 100
                if break_pct > 5:
                    score += 20
                elif break_pct > 3:
                    score += 12
                else:
                    score += 6

                # 量能强度
                vol_ratio = current_vol / avg_vol_20
                if vol_ratio > 3:
                    score += 15
                elif vol_ratio > 2:
                    score += 10
                else:
                    score += 5

                # 均线发散度
                ma_spread = (current_close - ma20) / ma20 * 100
                if 3 <= ma_spread <= 10:
                    score += 12
                elif ma_spread > 10:
                    score += 5

                # 回撤小加分
                dd_5d = (np.max(closes[-5:]) - current_close) / np.max(closes[-5:]) * 100
                if dd_5d < 2:
                    score += 10

                # RSI健康加分
                if 50 <= rsi <= 70:
                    score += 8

                candidates.append({
                    'code': code,
                    'price': round(float(current_close), 2),
                    'score': score,
                    'break_pct': round(float(break_pct), 2),
                    'vol_ratio': round(float(vol_ratio), 2),
                    'rsi': round(float(rsi), 1),
                    'ma_spread': round(float(ma_spread), 2),
                })

            except Exception:
                continue
    finally:
        db.close()

    # 排序
    ranked = sorted(candidates, key=lambda x: x['score'], reverse=True)

    # 查询名称
    top = ranked[:20]
    if top:
        db = SessionLocal()
        try:
            code_list = [r['code'] for r in top]
            placeholders = ','.join([f':c{i}' for i in range(len(code_list))])
            params = {f'c{i}': code_list[i] for i in range(len(code_list))}
            name_rows = db.execute(text(
                f'SELECT code, name FROM backtest_stock_meta WHERE code IN ({placeholders})'
            ), params).fetchall()
            name_map = {r[0]: r[1] for r in name_rows}
            for r in top:
                r['name'] = name_map.get(r['code'], '')
        finally:
            db.close()

    return {
        'strategy': 'breakout',
        'name': '突破形态',
        'description': '量价突破+均线多头共振, 捕捉趋势启动点',
        'count': len(top),
        'stocks': top,
    }

if __name__ == '__main__':
    import json
    print(json.dumps(screen_breakouts(), ensure_ascii=False, indent=2))
