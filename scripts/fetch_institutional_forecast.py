#!/usr/bin/env python3
"""
拉取单只 A 股的 2026 机构预测数据 → 写入 prediction_aggregates 表

数据源: East Money 数据中心 API
  - RPT_WEB_RESPREDICT: 机构评级 + EPS 预测 (2025A/2026E/2027E/2028E)
  - RPT_F10_FINANCE_GINCOME: 财务数据 (用于估算 net_profit)

Usage:
    python scripts/fetch_institutional_forecast.py --code 300433
    python scripts/fetch_institutional_forecast.py --codes 300433,300136
    python scripts/fetch_institutional_forecast.py --code 300433 --dry-run
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict, List

# 让脚本可以独立运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EAST_MONEY_API = "https://datacenter-web.eastmoney.com/api/data/v1/get"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://emweb.securities.eastmoney.com/",
    "Accept": "application/json",
}


def api_get(report_name: str, filters: str, page_size: int = 10, sort: str = "") -> Dict:
    url = (f"{EAST_MONEY_API}?reportName={report_name}"
           f"&columns=ALL&filter={filters}&pageSize={page_size}")
    if sort:
        url += f"&{sort}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get_analyst_forecast(code: str) -> Optional[Dict]:
    """从 RPT_WEB_RESPREDICT 获取机构 EPS 预测"""
    result = api_get("RPT_WEB_RESPREDICT",
                     f"(SECURITY_CODE%3D%22{code}%22)", page_size=1)
    if not result.get("success") or not result.get("result", {}).get("data"):
        return None
    return result["result"]["data"][0]


def get_actual_financials(code: str) -> Optional[Dict]:
    """从 RPT_F10_FINANCE_GINCOME 获取 2025年报 实际数据 (用于估算 net_profit)"""
    result = api_get("RPT_F10_FINANCE_GINCOME",
                     f"(SECURITY_CODE%3D%22{code}%22)", page_size=30,
                     sort="sortColumns=REPORT_DATE&sortTypes=-1")
    if not result.get("success"):
        return None
    data = result.get("result", {}).get("data", [])
    # 找最近一个年报 (REPORT_DATE = 12-31, REPORT_TYPE = 年报)
    annual = None
    for r in data:
        date = r.get("REPORT_DATE", "")[:10]
        if date.endswith("-12-31") and r.get("REPORT_TYPE") in ("年报", "年度"):
            annual = r
            break
    return annual


def determine_rating_label(buy: int, add: int, neutral: int, reduce: int, sale: int) -> str:
    """根据评级分布确定综合评级"""
    total = buy + add + neutral + reduce + sale
    if total == 0:
        return ""
    buy_pct = (buy + add) / total
    if buy_pct >= 0.7:
        return "买入"
    elif buy_pct >= 0.4:
        return "增持"
    elif buy_pct >= 0.15:
        return "中性"
    elif buy_pct > 0:
        return "减持"
    else:
        return "卖出"


def build_aggregate_row(code: str) -> Optional[Dict]:
    """组装一条 prediction_aggregates 行"""
    forecast = get_analyst_forecast(code)
    if not forecast:
        return None

    # EPS 预测 (元)
    eps_25 = float(forecast.get("EPS1") or 0)
    eps_26 = float(forecast.get("EPS2") or 0)
    eps_27 = float(forecast.get("EPS3") or 0)
    eps_28 = float(forecast.get("EPS4") or 0)

    # 估算 net_profit: 用 2025 实际 net_profit / 2025 实际 EPS 得到总股本
    # 然后 EPS_2026 × 总股本 = 估算 2026E net_profit
    actual = get_actual_financials(code)
    np_25_actual_yi = 0.0  # 单位: 亿
    actual_eps = 0.0
    if actual:
        np_25_actual_yi = float(actual.get("PARENT_NETPROFIT", 0) or 0) / 1e8
        actual_eps = float(actual.get("BASIC_EPS", 0) or 0)
        rev_25_actual = float(actual.get("TOTAL_OPERATE_INCOME", 0) or 0) / 1e8
    else:
        rev_25_actual = 0.0

    # 估算总股本 (亿股)
    total_shares_yi = 0.0
    if actual_eps > 0 and np_25_actual_yi > 0:
        total_shares_yi = np_25_actual_yi / actual_eps

    # 估算各年 net_profit
    def estimate_np(eps):
        if total_shares_yi > 0 and eps > 0:
            return round(eps * total_shares_yi, 2)
        return 0.0

    np_25 = round(np_25_actual_yi, 2) if np_25_actual_yi > 0 else estimate_np(eps_25)
    np_26 = estimate_np(eps_26)
    np_27 = estimate_np(eps_27)
    np_28 = estimate_np(eps_28)

    # 评级
    buy = int(forecast.get("RATING_BUY_NUM") or 0)
    add = int(forecast.get("RATING_ADD_NUM") or 0)
    neutral = int(forecast.get("RATING_NEUTRAL_NUM") or 0)
    reduce = int(forecast.get("RATING_REDUCE_NUM") or 0)
    sale = int(forecast.get("RATING_SALE_NUM") or 0)
    rating_label = determine_rating_label(buy, add, neutral, reduce, sale)
    analyst_count = int(forecast.get("RATING_ORG_NUM") or 0)

    return {
        "code": code,
        "eps_2025a": f"{eps_25:.3f}" if eps_25 else "",
        "eps_2026e": f"{eps_26:.3f}" if eps_26 else "",
        "eps_2027e": f"{eps_27:.3f}" if eps_27 else "",
        "eps_2028e": f"{eps_28:.3f}" if eps_28 else "",
        "net_profit_2025a": f"{np_25}亿" if np_25 else "",
        "net_profit_2026e": f"{np_26}亿" if np_26 else "",
        "net_profit_2027e": f"{np_27}亿" if np_27 else "",
        "net_profit_2028e": f"{np_28}亿" if np_28 else "",
        "revenue_2025a": f"{rev_25_actual}亿" if rev_25_actual else "",
        "revenue_2026e": "",  # 暂无营收预测
        "revenue_2027e": "",
        "revenue_2028e": "",
        "roe_2025a": "",  # 暂无 ROE 数据
        "roe_2026e": "",
        "roe_2027e": "",
        "roe_2028e": "",
        "rating_score": f"{(buy + add) / max(analyst_count, 1) * 5:.2f}" if analyst_count else "",
        "rating_label": rating_label,
        "analyst_count": str(analyst_count),
        "avg_pe_ttm": "",  # 暂无 PE_TTM 数据
        "updated_at": datetime.now().isoformat(),
    }


def save_to_db(row: Dict, dry_run: bool = False) -> bool:
    """写入 prediction_aggregates 表 (INSERT ... ON DUPLICATE KEY UPDATE)"""
    if dry_run:
        print(f"[DRY-RUN] {row['code']} ({row['rating_label']}, {row['analyst_count']}家覆盖):")
        for k, v in row.items():
            if v:
                print(f"  {k}: {v}")
        return True

    from sqlalchemy import text
    from models import get_db
    db = next(get_db())
    try:
        db.execute(text("""
            INSERT INTO prediction_aggregates
                (code, eps_2025a, eps_2026e, eps_2027e, eps_2028e,
                 net_profit_2025a, net_profit_2026e, net_profit_2027e, net_profit_2028e,
                 revenue_2025a, revenue_2026e, revenue_2027e, revenue_2028e,
                 roe_2025a, roe_2026e, roe_2027e, roe_2028e,
                 rating_score, rating_label, analyst_count, avg_pe_ttm, updated_at)
            VALUES
                (:code, :eps_2025a, :eps_2026e, :eps_2027e, :eps_2028e,
                 :net_profit_2025a, :net_profit_2026e, :net_profit_2027e, :net_profit_2028e,
                 :revenue_2025a, :revenue_2026e, :revenue_2027e, :revenue_2028e,
                 :roe_2025a, :roe_2026e, :roe_2027e, :roe_2028e,
                 :rating_score, :rating_label, :analyst_count, :avg_pe_ttm, :updated_at)
            ON DUPLICATE KEY UPDATE
                eps_2025a=VALUES(eps_2025a), eps_2026e=VALUES(eps_2026e),
                eps_2027e=VALUES(eps_2027e), eps_2028e=VALUES(eps_2028e),
                net_profit_2025a=VALUES(net_profit_2025a), net_profit_2026e=VALUES(net_profit_2026e),
                net_profit_2027e=VALUES(net_profit_2027e), net_profit_2028e=VALUES(net_profit_2028e),
                revenue_2025a=VALUES(revenue_2025a),
                rating_score=VALUES(rating_score), rating_label=VALUES(rating_label),
                analyst_count=VALUES(analyst_count), updated_at=VALUES(updated_at)
        """), row)
        db.commit()
        print(f"✓ {row['code']} ({row['rating_label']}, {row['analyst_count']}家覆盖) 已写入")
        return True
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="拉取 A 股机构预测数据")
    parser.add_argument("--code", help="单只股票代码 (如 300433)")
    parser.add_argument("--codes", help="多只股票代码, 逗号分隔")
    parser.add_argument("--dry-run", action="store_true", help="只打印不写库")
    args = parser.parse_args()

    codes = []
    if args.code:
        codes = [args.code]
    elif args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        parser.error("请指定 --code 或 --codes")

    success = 0
    for code in codes:
        try:
            row = build_aggregate_row(code)
            if not row:
                print(f"✗ {code}: 拉取失败 (机构预测数据可能不存在)")
                continue
            if save_to_db(row, dry_run=args.dry_run):
                success += 1
        except Exception as e:
            print(f"✗ {code}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n完成: {success}/{len(codes)} 成功")
    sys.exit(0 if success == len(codes) else 1)


if __name__ == "__main__":
    main()
