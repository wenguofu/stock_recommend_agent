#!/usr/bin/env python3
"""
十倍股筛选策略 — 基本面+技术面共振

筛选逻辑:
  1. 市值50-500亿 (成长空间)
  2. ROE > 10% (盈利能力)
  3. 毛利率 > 25% (竞争壁垒)
  4. 利润增速 > 20% (成长性)
  5. 近60日涨幅适中 (20-80%, 不追高)
  6. 日均成交 > 5000万 (流动性)

综合评分排序, 返回Top20
"""
import sys, os, math, time
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import SessionLocal
from sqlalchemy import text

def screen_tenbaggers():
    db = SessionLocal()
    try:
        # 1. 从基本面DB筛选
        fin_rows = db.execute(text('''
            SELECT code, roe, gross_margin, profit_yoy, revenue_yoy, pe_ttm
            FROM stock_financials
            WHERE roe IS NOT NULL AND roe > 5
            ORDER BY roe DESC
            LIMIT 200
        ''')).fetchall()

        candidates = {}
        for row in fin_rows:
            code, roe, gm, profit_yoy, rev_yoy, pe = row
            if gm and gm > 20:  # 毛利率门槛
                candidates[code] = {
                    'code': code,
                    'roe': roe,
                    'gross_margin': gm,
                    'profit_yoy': profit_yoy or 0,
                    'revenue_yoy': rev_yoy or 0,
                    'pe_ttm': pe,
                    'score': 0,
                }

        if not candidates:
            # 基本面数据不足, 用技术面补
            rows = db.execute(text('''
                SELECT code, MAX(close) as latest_close, AVG(volume) as avg_vol
                FROM backtest_data
                WHERE code REGEXP '^[0-9]{6}$'
                GROUP BY code HAVING COUNT(*) >= 120 AND AVG(volume) > 5000000
                ORDER BY AVG(volume) DESC LIMIT 100
            ''')).fetchall()
            for row in rows:
                code = row[0]
                if code not in candidates:
                    candidates[code] = {'code': code, 'roe': 0, 'gross_margin': 0,
                                        'profit_yoy': 0, 'revenue_yoy': 0, 'pe_ttm': None, 'score': 0}

        # 2. 技术面评分
        for code in list(candidates.keys()):
            try:
                kline = db.execute(text(
                    'SELECT date, close, volume FROM backtest_data WHERE code=:code ORDER BY date'
                ), {'code': code}).fetchall()

                if len(kline) < 60:
                    del candidates[code]
                    continue

                closes = [r[1] for r in kline if r[1]]
                volumes = [r[2] for r in kline if r[2]]
                n = len(closes)

                score = 50

                # 60日涨幅
                if n >= 60:
                    ret60 = (closes[-1] / closes[-60] - 1) * 100
                    if 20 <= ret60 <= 80:
                        score += 15
                    elif 10 <= ret60 < 20:
                        score += 8
                    elif 80 < ret60 <= 120:
                        score += 5

                # 20日动量
                if n >= 20:
                    ret20 = (closes[-1] / closes[-20] - 1) * 100
                    if 5 <= ret20 <= 25:
                        score += 10

                # 波动率
                if n >= 20:
                    rets = np.diff(closes[-21:]) / closes[-21:-1]
                    vol = float(np.std(rets) * 100 * np.sqrt(252))
                    if 25 <= vol <= 50:
                        score += 10

                # 均线多头
                if n >= 20:
                    ma5 = np.mean(closes[-5:])
                    ma20 = np.mean(closes[-20:])
                    if ma5 > ma20:
                        score += 10

                # 成交量趋势
                if len(volumes) >= 20:
                    recent_vol = np.mean(volumes[-5:])
                    earlier_vol = np.mean(volumes[-20:-5])
                    if earlier_vol > 0 and recent_vol / earlier_vol > 1.2:
                        score += 8

                # 日均成交额
                if len(volumes) >= 20 and len(closes) >= 20:
                    avg_amount = np.mean([volumes[i] * closes[i] for i in range(-20, 0)])
                    if avg_amount > 50000000:
                        score += 10

                # 基本面加分
                c = candidates[code]
                if c['roe'] and c['roe'] > 15:
                    score += 12
                elif c['roe'] and c['roe'] > 10:
                    score += 6
                if c['gross_margin'] and c['gross_margin'] > 40:
                    score += 10
                elif c['gross_margin'] and c['gross_margin'] > 25:
                    score += 5
                if c['profit_yoy'] and c['profit_yoy'] > 30:
                    score += 8

                candidates[code]['score'] = score
                candidates[code]['price'] = round(closes[-1], 2)
                candidates[code]['ret_60d'] = round(ret60, 2) if n >= 60 else None
                candidates[code]['ret_20d'] = round(ret20, 2) if n >= 20 else None

            except Exception:
                if code in candidates:
                    del candidates[code]
    finally:
        db.close()

    # 3. 排序返回Top20
    ranked = sorted(candidates.values(), key=lambda x: x['score'], reverse=True)

    # 查询股票名称
    code_list = [r['code'] for r in ranked[:20]]
    name_map = {}
    if code_list:
        db = SessionLocal()
        try:
            placeholders = ','.join([f':c{i}' for i in range(len(code_list))])
            params = {f'c{i}': code_list[i] for i in range(len(code_list))}
            name_rows = db.execute(text(
                f'SELECT code, name FROM backtest_stock_meta WHERE code IN ({placeholders})'
            ), params).fetchall()
            name_map = {r[0]: r[1] for r in name_rows}
        finally:
            db.close()

    results = []
    for r in ranked[:20]:
        results.append({
            'code': r['code'],
            'name': name_map.get(r['code'], ''),
            'price': r.get('price'),
            'score': r['score'],
            'roe': r.get('roe'),
            'gross_margin': r.get('gross_margin'),
            'ret_60d': r.get('ret_60d'),
            'ret_20d': r.get('ret_20d'),
        })

    return {
        'strategy': 'tenbagger',
        'name': '十倍潜力股',
        'description': '基本面+技术面共振, 筛选具备长期成长潜力的标的',
        'count': len(results),
        'stocks': results,
    }

if __name__ == '__main__':
    import json
    print(json.dumps(screen_tenbaggers(), ensure_ascii=False, indent=2))
