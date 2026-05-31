#!/usr/bin/env python3
"""
基本面数据拉取脚本 — 东方财富 DataCenter API 直连

用法:
  python3 scripts/fetch_fundamentals.py --code 600487          # 单只股票
  python3 scripts/fetch_fundamentals.py --codes 600487,000001  # 多只（逗号分隔）
  python3 scripts/fetch_fundamentals.py --watchlist             # 全部自选股
  python3 scripts/fetch_fundamentals.py --file stocks.txt       # 从文件读取（每行一个代码）
  python3 scripts/fetch_fundamentals.py --force                 # 强制刷新（忽略已有数据）
  python3 scripts/fetch_fundamentals.py --dry-run               # 只检查不拉取
  python3 scripts/fetch_fundamentals.py --delay 3               # 自定义间隔秒数

数据源:
  东方财富 RPT_F10_FINANCE_MAINFINADATA (165字段)
  包含: EPS, ROE, 毛利率, 营收, 净利润, 营收同比, 利润同比

存储:
  MySQL stock_financials 表 (通过 DATABASE_URL 环境变量)
"""
import sys
import os
import time
import random
import argparse
import requests
import urllib3
urllib3.disable_warnings()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from models import SessionLocal, StockFinancial
from sqlalchemy import text
from datetime import datetime


# ── API 配置 ──
API_URL = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
COLUMNS = (
    'SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,REPORT_TYPE,'
    'EPSJB,ROEJQ,XSMLL,TOTALOPERATEREVE,PARENTNETPROFIT,'
    'TOTALOPERATEREVETZ,PARENTNETPROFITTZ,MLR'
)

session = requests.Session()
session.verify = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://emweb.securities.eastmoney.com/',
})


def parse_val(v):
    """安全转 float"""
    if v is None or v == '':
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def fetch_indicators(code):
    """从东方财富拉取主要财务指标"""
    params = {
        'reportName': 'RPT_F10_FINANCE_MAINFINADATA',
        'columns': COLUMNS,
        'pageSize': 5,
        'sortColumns': 'REPORT_DATE',
        'sortTypes': -1,
        'filter': f'(SECURITY_CODE="{code}")',
        'source': 'WEB', 'client': 'WEB',
    }
    try:
        r = session.get(API_URL, params=params, timeout=15, verify=False)
        if r.status_code == 200:
            result = r.json()
            if result.get('success') and result.get('result'):
                return result['result'].get('data', [])
    except Exception as e:
        print(f"    API error: {e}")
    return []


def fetch_balance(code, report_date):
    """拉取资产负债表"""
    params = {
        'reportName': 'RPT_DMSK_FN_BALANCE',
        'columns': 'TOTAL_ASSETS,TOTAL_EQUITY',
        'pageSize': 1,
        'sortColumns': 'REPORT_DATE',
        'sortTypes': -1,
        'filter': f'(SECURITY_CODE="{code}")(REPORT_DATE=\'{report_date}\')',
        'source': 'WEB', 'client': 'WEB',
    }
    try:
        r = session.get(API_URL, params=params, timeout=15, verify=False)
        if r.status_code == 200:
            result = r.json()
            if result.get('success') and result.get('result') and result['result'].get('data'):
                return result['result']['data'][0]
    except Exception:
        pass
    return {}


def save_one(db, code, row, balance_row=None):
    """保存单条财务数据（去重）"""
    report_date = str(row.get('REPORT_DATE', ''))[:10]
    if not report_date:
        return None

    existing = db.query(StockFinancial).filter(
        StockFinancial.code == code,
        StockFinancial.report_date == report_date
    ).first()
    if existing:
        return existing

    fin = StockFinancial(
        code=code,
        report_date=report_date,
        report_type=str(row.get('REPORT_TYPE', ''))[:10],
        revenue=parse_val(row.get('TOTALOPERATEREVE')),
        net_profit=parse_val(row.get('PARENTNETPROFIT')),
        gross_profit=parse_val(row.get('MLR')),
        eps=parse_val(row.get('EPSJB')),
        roe=parse_val(row.get('ROEJQ')),
        gross_margin=parse_val(row.get('XSMLL')),
        revenue_yoy=parse_val(row.get('TOTALOPERATEREVETZ')),
        profit_yoy=parse_val(row.get('PARENTNETPROFITTZ')),
        total_assets=parse_val(balance_row.get('TOTAL_ASSETS')) if balance_row else None,
        created_at=datetime.now(),
    )
    db.add(fin)
    db.commit()
    return fin


def pull_fundamentals(codes, force=False, dry_run=False, delay=3.0):
    """
    拉取多只股票的基本面数据

    Args:
        codes: 股票代码列表
        force: 强制刷新（忽略已有数据）
        dry_run: 只检查不拉取
        delay: 请求间隔秒数（避免限流）

    Returns:
        dict: {ok: int, skip: int, fail: int, codes: list}
    """
    db = SessionLocal()
    ok = 0
    skip = 0
    fail = 0
    failed_codes = []
    updated_codes = []

    for i, code in enumerate(codes):
        status = f"[{i+1}/{len(codes)}] {code}"
        action = ""

        # 检查是否有最近数据
        if not force:
            latest = db.execute(text(
                "SELECT MAX(report_date) FROM stock_financials WHERE code=:code"
            ), {'code': code}).scalar()
            if latest and latest >= '2026-03-31':
                print(f"{status}: ✅ 已有 ({latest})")
                skip += 1
                continue

        if dry_run:
            print(f"{status}: 🔍 需更新")
            skip += 1
            updated_codes.append(code)
            continue

        # 拉取
        print(f"{status}: 📡", end="", flush=True)
        rows = fetch_indicators(code)

        if not rows:
            print(f"\r{status}: ⚠️ 无数据")
            fail += 1
            failed_codes.append(code)
            time.sleep(random.uniform(2, delay))
            continue

        saved = 0
        for row in rows:
            rd = str(row.get('REPORT_DATE', ''))[:10]
            # 只存年报和一季报
            if '12-31' not in rd and '-03-31' not in rd:
                continue

            bal = None
            try:
                bal = fetch_balance(code, rd)
            except Exception:
                pass

            fin = save_one(db, code, row, bal)
            if fin:
                saved += 1

        if saved > 0:
            # Get name
            name_row = db.execute(text(
                "SELECT name FROM watchlist WHERE code=:code"
            ), {'code': code}).fetchone()
            name = name_row[0] if name_row and name_row[0] else ''
            eps = rows[0].get('EPSJB', '-') if rows else '-'
            roe = rows[0].get('ROEJQ', '-') if rows else '-'
            print(f"\r{status} {name}: ✅ {saved}期 EPS={eps} ROE={roe}")
            ok += 1
            updated_codes.append(code)
        else:
            print(f"\r{status}: ⚠️ 无新数据")
            fail += 1
            failed_codes.append(code)

        time.sleep(random.uniform(delay - 1, delay + 1))

    db.close()

    print(f"\n{'='*50}")
    print(f"📊 完成: ok={ok} skip={skip} fail={fail}")
    if updated_codes:
        print(f"✅ 已更新: {', '.join(updated_codes)}")
    if failed_codes:
        print(f"❌ 失败: {', '.join(failed_codes)}")

    return {'ok': ok, 'skip': skip, 'fail': fail, 'updated': updated_codes, 'failed': failed_codes}


def main():
    parser = argparse.ArgumentParser(
        description='拉取A股基本面数据到 MySQL stock_financials 表',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --code 600487              # 单只股票
  %(prog)s --codes 600487,000001      # 多只（逗号分隔）
  %(prog)s --watchlist                 # 自选股全部
  %(prog)s --file stocks.txt           # 从文件读取
  %(prog)s --watchlist --force         # 强制刷新全部自选股
  %(prog)s --watchlist --dry-run       # 只检查哪些需要更新
        """
    )
    parser.add_argument('--code', type=str, help='单只股票代码')
    parser.add_argument('--codes', type=str, help='多只股票代码（逗号分隔）')
    parser.add_argument('--watchlist', action='store_true', help='拉取全部自选股')
    parser.add_argument('--file', type=str, help='从文件读取股票代码（每行一个）')
    parser.add_argument('--force', action='store_true', help='强制刷新（忽略已有数据）')
    parser.add_argument('--dry-run', action='store_true', help='只检查不拉取')
    parser.add_argument('--delay', type=float, default=3.0, help='请求间隔秒数（默认3）')
    parser.add_argument('--include-688', action='store_true', help='包含科创板')

    args = parser.parse_args()

    codes = []
    if args.code:
        codes = [args.code.strip()]
    elif args.codes:
        codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    elif args.watchlist:
        db = SessionLocal()
        try:
            query = "SELECT code FROM watchlist WHERE code NOT LIKE 'SE'"
            if not args.include_688:
                query += " AND code NOT LIKE '688%'"
            codes = [r[0] for r in db.execute(text(query)).fetchall()]
        finally:
            db.close()
        print(f"自选股: {len(codes)} 只")
    elif args.file:
        with open(args.file) as f:
            codes = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        print(f"文件 {args.file}: {len(codes)} 只")
    else:
        parser.print_help()
        sys.exit(1)

    if not codes:
        print("❌ 未找到任何股票")
        sys.exit(1)

    pull_fundamentals(codes, force=args.force, dry_run=args.dry_run, delay=args.delay)


if __name__ == '__main__':
    main()
