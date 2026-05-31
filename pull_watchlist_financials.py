#!/usr/bin/env python3
"""拉取自选股基本面数据 — 东方财富API直连"""
import sys, os, time, random, requests, urllib3
urllib3.disable_warnings()

sys.path.insert(0, os.path.dirname(__file__))
from models import SessionLocal, StockFinancial
from sqlalchemy import text
from datetime import datetime

# ── API config ──
MAIN_URL = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
BALANCE_URL = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
INCOME_URL = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'

session = requests.Session()
session.verify = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://emweb.securities.eastmoney.com/',
})


def fetch_main_indicators(code):
    """拉取主要财务指标(ROE/EPS/毛利率等)"""
    params = {
        'reportName': 'RPT_F10_FINANCE_MAINFINADATA',
        'columns': 'SECURITY_CODE,SECURITY_NAME_ABBR,REPORT_DATE,REPORT_TYPE,'
                   'EPSJB,ROEJQ,XSMLL,TOTALOPERATEREVE,PARENTNETPROFIT,'
                   'TOTALOPERATEREVETZ,PARENTNETPROFITTZ,MLR',
        'pageSize': 5,  # 最近5期
        'sortColumns': 'REPORT_DATE',
        'sortTypes': -1,
        'filter': f'(SECURITY_CODE="{code}")',
        'source': 'WEB', 'client': 'WEB',
    }
    try:
        r = session.get(MAIN_URL, params=params, timeout=15)
        if r.status_code == 200:
            result = r.json()
            if result.get('success') and result.get('result'):
                return result['result'].get('data', [])
    except Exception as e:
        print(f"    API error: {e}")
    return []


def fetch_balance_data(code, report_date):
    """拉取资产负债表(总资产)"""
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
        r = session.get(BALANCE_URL, params=params, timeout=15)
        if r.status_code == 200:
            result = r.json()
            if result.get('success') and result.get('result') and result['result'].get('data'):
                return result['result']['data'][0]
    except Exception:
        pass
    return {}


def parse_val(v):
    """安全转float"""
    if v is None or v == '':
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def save_financial(db, code, row, balance_row=None):
    """保存/更新一条财务数据"""
    report_date = str(row.get('REPORT_DATE', ''))[:10]
    if not report_date:
        return None

    # 检查是否已存在
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
        revenue=parse_val(row.get('TOTALOPERATEREVE')),  # 营业收入
        net_profit=parse_val(row.get('PARENTNETPROFIT')),  # 归母净利润
        gross_profit=parse_val(row.get('MLR')),  # 毛利
        eps=parse_val(row.get('EPSJB')),  # 每股收益
        roe=parse_val(row.get('ROEJQ')),  # ROE
        gross_margin=parse_val(row.get('XSMLL')),  # 毛利率
        net_margin=None,  # 可从income statement算
        pe_ttm=None,  # 需要从行情数据算
        pb=None,
        pe_industry=None,
        pb_industry=None,
        revenue_yoy=parse_val(row.get('TOTALOPERATEREVETZ')),  # 营收同比
        profit_yoy=parse_val(row.get('PARENTNETPROFITTZ')),  # 利润同比
        total_assets=parse_val(balance_row.get('TOTAL_ASSETS')) if balance_row else None,
        created_at=datetime.now(),
    )
    db.add(fin)
    db.commit()
    db.refresh(fin)
    return fin


# ── Main ──
db = SessionLocal()

# 获取所有自选股 (A股)
watchlist = db.execute(text(
    "SELECT code, name FROM watchlist WHERE code NOT LIKE 'SE' AND code NOT LIKE '688%'"
)).fetchall()

print(f"自选股: {len(watchlist)} 只\n")

ok = 0
skip = 0
fail = 0

for i, (code, name) in enumerate(watchlist):
    print(f"[{i+1}/{len(watchlist)}] {code} {name or ''}:", end=" ", flush=True)

    # 检查是否已有最近数据
    latest = db.execute(text(
        "SELECT MAX(report_date) FROM stock_financials WHERE code=:code"
    ), {'code': code}).scalar()

    if latest and latest >= '2026-03-31':
        print(f"✅ 已有数据 ({latest})")
        skip += 1
        continue

    # 拉取
    rows = fetch_main_indicators(code)
    if not rows:
        print("⚠️ 无API数据")
        fail += 1
        time.sleep(random.uniform(2, 4))
        continue

    saved = 0
    for row in rows:
        report_date = str(row.get('REPORT_DATE', ''))[:10]
        # 只存年报和一季报（最重要）
        if '12-31' not in report_date and '-03-31' not in report_date:
            continue

        # 拉取资产负债表 (年报才有完整数据)
        bal = None
        try:
            bal = fetch_balance_data(code, report_date)
        except Exception:
            pass

        fin = save_financial(db, code, row, bal)
        if fin:
            saved += 1

    if saved > 0:
        print(f"✅ {saved}期数据")
        ok += 1
    else:
        print("⚠️ 无新数据")
        fail += 1

    # 慢速拉取
    time.sleep(random.uniform(2, 4))

db.close()
print(f"\n完成: ok={ok} skip={skip} fail={fail}")
