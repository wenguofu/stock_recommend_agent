#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐股补全历史日K线数据（东方财富API直连版）
- 遍历 backtest_stock_meta 中所有股票
- 每次请求间隔 3-5s，避免限流

用法：
  python3 fill_missing_data.py                   # 补全全部
  python3 fill_missing_data.py --stock 600487    # 只补单只（测试用）
  python3 fill_missing_data.py --dry-run         # 只检查不拉取
  python3 fill_missing_data.py --limit 100       # 最多处理100只
"""
import os
import sys
import time
import json
import random
import argparse
import requests
from datetime import date, datetime, timedelta

PROJECT_DIR = os.path.dirname(__file__)
sys.path.insert(0, PROJECT_DIR)

parser = argparse.ArgumentParser(description="逐股补全历史日K线数据")
parser.add_argument("--stock", type=str, help="只拉取指定的股票代码")
parser.add_argument("--dry-run", action="store_true", help="只检查不拉取")
parser.add_argument("--delay-min", type=float, default=3.0, help="最小请求间隔（秒），默认3")
parser.add_argument("--delay-max", type=float, default=5.0, help="最大请求间隔（秒），默认5")
parser.add_argument("--limit", type=int, default=0, help="最多处理N只股票，0=不限制")
args = parser.parse_args()

# ── HTTP Session ──
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://quote.eastmoney.com/',
})

# ── 连接数据库 ──
from models import SessionLocal
from db import save_backtest_data_batch, save_backtest_meta

db = SessionLocal()

# ── 获取待处理股票列表 ──
from models import BacktestStockMeta
if args.stock:
    metas = db.query(BacktestStockMeta).filter(BacktestStockMeta.code == args.stock).all()
    if not metas:
        print(f"❌ 未找到股票: {args.stock}")
        sys.exit(1)
else:
    metas = db.query(BacktestStockMeta).order_by(BacktestStockMeta.last_updated.asc()).all()

print(f"📊 待处理股票: {len(metas)} 只")
print(f"   间隔: {args.delay_min}-{args.delay_max}s")
print(f"   数据源: 东方财富 (push2his.eastmoney.com)")
if args.dry_run:
    print("   🔍 DRY-RUN 模式：只检查不拉取")

# ── 检查数据 ──
from models import BacktestData

def check_stock_data(code):
    """检查股票数据完整性"""
    rows = db.query(BacktestData).filter(
        BacktestData.code == code
    ).order_by(BacktestData.date).all()
    count = len(rows)
    if count == 0:
        return count, None, None
    return count, rows[0].date, rows[-1].date


def fetch_stock_history(code):
    """从东方财富拉取完整历史日K线（前复权）"""
    # 确定市场代码: 0=深圳 1=上海
    if code.startswith(('6', '5', '9')):
        secid = f'1.{code}'
    else:
        secid = f'0.{code}'

    today_str = date.today().strftime('%Y%m%d')
    begin_str = '20100101'  # 从2010年开始保证完整

    url = (
        f'https://push2his.eastmoney.com/api/qt/stock/kline/get'
        f'?secid={secid}'
        f'&fields1=f1,f2,f3,f4,f5,f6'
        f'&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'
        f'&klt=101'        # 日K
        f'&fqt=1'          # 前复权
        f'&beg={begin_str}'
        f'&end={today_str}'
        f'&lmt=3000'       # 最多3000条，足够覆盖
    )

    resp = session.get(url, timeout=30)
    if resp.status_code != 200:
        return []

    data = resp.json()
    if data.get('rc') != 0 or not data.get('data'):
        return []

    klines = data['data'].get('klines', [])
    if not klines:
        return []

    records = []
    for line in klines:
        parts = line.split(',')
        if len(parts) < 11:
            continue
        # 格式: 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
        records.append({
            'date': parts[0],
            'open': float(parts[1]),
            'close': float(parts[2]),
            'high': float(parts[3]),
            'low': float(parts[4]),
            'volume': float(parts[5]),
            'amount': float(parts[6]),
            'change_pct': float(parts[8]),
            'turnover': float(parts[10]),
            'source': 'eastmoney',
        })

    return records


# ── 主循环 ──
processed = 0
skipped = 0
failed = 0
updated = 0
start_time = time.time()

for i, meta in enumerate(metas):
    code = meta.code
    name = meta.name or ""

    # 检查当前数据
    count, data_start, data_end = check_stock_data(code)

    # 判断是否跳过：数据>=200条且最后日期是最近3个交易日
    today_str = date.today().strftime('%Y-%m-%d')
    needs_fetch = True

    if count >= 200 and data_end and data_end >= '2026-05-26':
        print(f"[{i+1}/{len(metas)}] {code} {name:<8} ✅ {count}条 (最新{data_end})  — 跳过")
        skipped += 1
        needs_fetch = False

    if not needs_fetch:
        if args.limit and updated >= args.limit:
            break
        continue

    # 需要拉取
    status = f"{count}条" if count > 0 else "空"
    if data_end:
        status += f" (~{data_end})"

    if args.dry_run:
        print(f"[{i+1}/{len(metas)}] {code} {name:<8} 🔍 需补数据 ({status})")
        skipped += 1
        if args.limit and skipped >= args.limit:
            break
        continue

    # 实际拉取
    records = []
    print(f"[{i+1}/{len(metas)}] {code} {name:<8} 📡 ({status}) ...", end="", flush=True)
    try:
        records = fetch_stock_history(code)
        if records:
            saved = save_backtest_data_batch(db, code, records)
            # 更新元信息
            dates = [r["date"] for r in records]
            save_backtest_meta(
                db, code, meta.name or code, meta.sector or "",
                data_start=min(dates), data_end=max(dates),
                total_days=len(records),
            )
            print(f"\r[{i+1}/{len(metas)}] {code} {name:<8} ✅ {count:>4}→{len(records):<5}条 "
                  f"({min(dates)} ~ {max(dates)})")
            updated += 1
        else:
            print(f"\r[{i+1}/{len(metas)}] {code} {name:<8} ⚠️ 无数据")
            failed += 1
    except Exception as e:
        print(f"\r[{i+1}/{len(metas)}] {code} {name:<8} ❌ {e}")
        failed += 1
        db.rollback()
        time.sleep(random.uniform(5, 10))

    processed += 1

    # 间隔休眠
    if records:
        delay = random.uniform(args.delay_min, args.delay_max)
        time.sleep(delay)
    else:
        time.sleep(random.uniform(1, 2))  # 失败了也短休眠

    if args.limit and updated >= args.limit:
        print(f"\n已处理 {args.limit} 只，结束")
        break

# ── 总结 ──
elapsed = time.time() - start_time
print(f"\n{'='*50}")
print(f"📊 完成")
print(f"   扫描: {i+1}  更新: {updated}  跳过: {skipped}  失败: {failed}")
print(f"   耗时: {elapsed/60:.1f} 分钟")

db.close()
