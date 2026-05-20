#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
回测数据预取脚本 — 缓存热门板块股票的历史日K线

工作流程：
  1. 读取 sector_data/ 获取最近N个热门板块
  2. 从这些板块提取股票名称 → 查代码（akshare全市场列表）
  3. akshare批量拉取1年日K线（含换手率）
  4. 存入 backtest_data 表
  5. 更新 backtest_stock_meta 元信息

用法：
  uv run python prefetch_backtest_data.py                    # 默认5个热门板块
  uv run python prefetch_backtest_data.py --top=10            # 取10个板块
  uv run python prefetch_backtest_data.py --stock=300750      # 手动指定股票
  uv run python prefetch_backtest_data.py --status            # 查看缓存状态
  uv run python prefetch_backtest_data.py --clear             # 清空缓存
  uv run python prefetch_backtest_data.py --refresh-all       # 刷新所有缓存
"""

import json
import os
import sys
import time
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

import pandas as pd
import numpy as np
import urllib.request

logging.basicConfig(level=logging.INFO, format="[Prefetch] %(message)s")
log = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(__file__)
SECTOR_DIR = os.path.join(PROJECT_DIR, "sector_data")


# ═══════════════════════════════════════════════
# 1. 从板块文件提取股票名
# ═══════════════════════════════════════════════

def get_hot_sectors(top_n: int = 5) -> List[Dict]:
    """读取最新板块数据，获取TOP N热门板块的股票列表"""
    if not os.path.exists(SECTOR_DIR):
        log.warning(f"板块数据目录不存在: {SECTOR_DIR}")
        return []

    files = sorted([f for f in os.listdir(SECTOR_DIR) if f.endswith(".json")])
    if not files:
        log.warning("无板块数据文件")
        return []

    latest = files[-1]
    with open(os.path.join(SECTOR_DIR, latest), encoding="utf-8") as f:
        data = json.load(f)

    sectors = data.get("sectors", [])
    result = []
    for i, s in enumerate(sectors[:top_n]):
        stocks_text = s.get("stocks", "")
        names = [n.strip() for n in stocks_text.replace("、", ",").split(",") if n.strip()]
        result.append({
            "rank": i + 1,
            "name": s["name"],
            "stock_names": names,
        })
        log.info(f"  板块#{i+1} {s['name']}: {names}")

    return result


def get_sector_stocks_flat(top_n: int = 5) -> List[str]:
    """获取所有热门板块的股票名（去重平铺）"""
    sectors = get_hot_sectors(top_n)
    seen = set()
    all_names = []
    for s in sectors:
        for name in s["stock_names"]:
            if name not in seen:
                seen.add(name)
                all_names.append(name)
    return all_names


# ═══════════════════════════════════════════════
# 2. 股票名→代码映射（全市场）
# ═══════════════════════════════════════════════

_name_code_cache = None


def build_name_to_code_map() -> Dict[str, str]:
    """建立 A 股股票名→代码 映射（akshare全市场列表）"""
    global _name_code_cache
    if _name_code_cache:
        return _name_code_cache

    mapping = {}

    # 方案A：akshare 全市场代码名称列表（独立数据源，不依赖东方财富行情）
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()  # 返回 code + name
        for _, row in df.iterrows():
            name = str(row.get("name", "")).strip()
            code = str(row.get("code", "")).strip()
            if name and code:
                mapping[name] = code
        log.info(f"akshare全市场列表: {len(mapping)} 条映射")
        _name_code_cache = mapping
        return mapping
    except ImportError:
        log.warning("akshare 未安装")
    except Exception as e:
        log.warning(f"akshare 全市场列表失败: {e}")

    # 方案B：逐个查询新浪实时行情（按名字找代码）
    log.info("使用逐个查询模式...")
    for _ in range(3):
        pass
    _name_code_cache = mapping
    return mapping


def quick_lookup_code(name: str) -> Optional[str]:
    """快速查单只股票代码（通过实时行情）"""
    try:
        suffix = f"sz{name}"
        url = f"http://qt.gtimg.cn/q={suffix}"
        req = urllib.request.urlopen(url, timeout=5)
        raw = req.read().decode("gbk")
        parts = raw.split("~")
        if len(parts) >= 3:
            # parts[1] = name, parts[2] = code
            if parts[1].strip() == name:
                return parts[2].strip()
    except:
        pass
    return None


# ═══════════════════════════════════════════════
# 3. 单只股票数据拉取（含重试）
# ═══════════════════════════════════════════════

def fetch_stock_data(code: str, name: str, days: int = 365) -> List[Dict]:
    """拉取单只股票历史数据，含3次重试
    
    Args:
        code: 股票代码
        name: 股票名（仅日志用）
        days: 拉取天数
    
    Returns:
        list[dict]: [{date, open, close, high, low, volume, amount, change_pct, turnover}, ...]
    """
    end = date.today()
    start = end - timedelta(days=int(days * 1.5))

    # 尝试 akshare
    for attempt in range(3):
        try:
            import akshare as ak
            df = ak.stock_zh_a_hist(
                symbol=code, period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if df is not None and not df.empty:
                col_map = {
                    "日期": "date", "开盘": "open", "收盘": "close",
                    "最高": "high", "最低": "low", "成交量": "volume",
                    "成交额": "amount", "振幅": "amplitude",
                    "涨跌幅": "change_pct", "涨跌额": "change_amount",
                    "换手率": "turnover",
                }
                df = df.rename(columns=col_map)
                keep = ["date", "open", "close", "high", "low", "volume",
                        "amount", "change_pct", "turnover"]

                records = []
                for _, row in df.iterrows():
                    rec = {"source": "akshare"}
                    for col in keep:
                        val = row.get(col, 0)
                        try:
                            if col == "date":
                                rec[col] = str(row["date"])[:10]
                            elif col == "turnover":
                                rec[col] = float(val)  # akshare返回的换手率已经是百分比
                            else:
                                rec[col] = float(val)
                        except (ValueError, TypeError):
                            rec[col] = 0.0
                    records.append(rec)

                # 截取指定天数
                if len(records) > days:
                    records = records[-days:]

                return records
        except ImportError:
            break
        except Exception as e:
            log.warning(f"   {name}({code}) attempt {attempt+1}: {e}")
            time.sleep(2)

    # 备选：Sina API
    try:
        sina_code = f"sh{code}" if code.startswith(("5", "6", "9")) else f"sz{code}"
        url = (f"http://money.finance.sina.com.cn/quotes_service/api/"
               f"json_v2.php/CN_MarketData.getKLineData?"
               f"symbol={sina_code}&scale=240&ma=no&datalen={min(days, 1023)}")

        req = urllib.request.urlopen(url, timeout=15)
        data = json.loads(req.read().decode())

        if not data or not isinstance(data, list):
            return []

        records = []
        closes = [float(d.get("close", 0)) for d in data]
        for i, d in enumerate(data):
            cp = 0.0
            if i > 0 and closes[i-1] > 0:
                cp = (closes[i] - closes[i-1]) / closes[i-1] * 100
            records.append({
                "date": d.get("day", "")[:10],
                "open": float(d.get("open", 0)),
                "close": closes[i],
                "high": float(d.get("high", 0)),
                "low": float(d.get("low", 0)),
                "volume": float(d.get("volume", 0)),
                "amount": 0,
                "change_pct": round(cp, 2),
                "turnover": 0,  # Sina无换手率
                "source": "sina",
            })

        if len(records) > days:
            records = records[-days:]
        return records
    except Exception as e:
        log.warning(f"   {name}({code}) Sina备选也失败: {e}")

    return []


# ═══════════════════════════════════════════════
# 4. 写入数据库
# ═══════════════════════════════════════════════

def save_to_db(code: str, name: str, sector: str, records: List[Dict]):
    """保存到回测缓存数据库"""
    if not records:
        return

    from models import SessionLocal
    from db import save_backtest_data_batch, save_backtest_meta, clear_backtest_data

    db = SessionLocal()
    try:
        # 先清旧数据，再写新的（防重复）
        clear_backtest_data(db, code)

        # 批量写入
        saved = save_backtest_data_batch(db, code, records)
        log.info(f"   写入数据库: {saved} 条")

        # 更新元信息
        dates = [r["date"] for r in records]
        save_backtest_meta(
            db, code, name, sector,
            data_start=min(dates),
            data_end=max(dates),
            total_days=len(records),
        )
    finally:
        db.close()


# ═══════════════════════════════════════════════
# 5. 主流程
# ═══════════════════════════════════════════════

def prefetch_all(top_n: int = 5, days: int = 365, manual_stocks: List[str] = None):
    """预取数据主流程"""
    print(f"\n{'='*60}")
    print(f"📥 回测数据预取")
    print(f"   板块数: TOP {top_n}")
    print(f"   天数: {days}")
    print(f"{'='*60}")

    # 1. 获取股票列表
    stock_list = []  # [(code, name, sector), ...]

    if manual_stocks:
        # 手动指定的股票
        build_name_to_code_map()
        for item in manual_stocks:
            if ":" in item:
                code, name = item.split(":", 1)
                stock_list.append((code.strip(), name.strip(), "手动"))
            else:
                stock_list.append((item.strip(), item.strip(), "手动"))
    else:
        # 从板块获取
        sectors = get_hot_sectors(top_n)
        mapping = build_name_to_code_map()

        for sector in sectors:
            for name in sector["stock_names"]:
                code = mapping.get(name)
                if not code:
                    code = quick_lookup_code(name)
                if code:
                    stock_list.append((code, name, sector["name"]))
                else:
                    log.warning(f"   未找到股票: {name}")

    # 2. 去重
    seen = set()
    unique_stocks = []
    for code, name, sector in stock_list:
        if code not in seen:
            seen.add(code)
            unique_stocks.append((code, name, sector))

    print(f"\n共 {len(unique_stocks)} 只股票需预取：")
    for code, name, sector in unique_stocks:
        print(f"   {code} {name} ({sector})")

    # 3. 逐只拉取
    success = 0
    fail = 0
    for i, (code, name, sector) in enumerate(unique_stocks, 1):
        print(f"\n[{i}/{len(unique_stocks)}] {name}({code}) - {sector}")
        records = fetch_stock_data(code, name, days)

        if records:
            print(f"   获取 {len(records)} 天数据 (含换手率: {records[-1].get('turnover', 0) > 0})")
            save_to_db(code, name, sector, records)
            success += 1
        else:
            print(f"   ❌ 获取失败")
            fail += 1

        # 间隔避免限流
        if i < len(unique_stocks):
            time.sleep(1.5)

    # 4. 汇总
    print(f"\n{'='*60}")
    print(f"✅ 预取完成: {success} 成功 / {fail} 失败 / {len(unique_stocks)} 总计")
    print(f"{'='*60}")


def show_status():
    """显示缓存状态"""
    from models import SessionLocal, BacktestStockMeta

    db = SessionLocal()
    try:
        metas = db.query(BacktestStockMeta).order_by(BacktestStockMeta.last_updated.desc()).all()
    finally:
        db.close()

    if not metas:
        print("📭 缓存为空，暂无已缓存股票")
        return

    print(f"\n📊 回测缓存状态 ({len(metas)} 只股票)")
    print(f"{'代码':>8s} {'名称':10s} {'板块':20s} {'起始':12s} {'截至':12s} {'天数':>5s} {'更新':>12s}")
    print(f"{'-'*75}")
    for m in metas:
        last_upd = m.last_updated.strftime("%m-%d %H:%M") if m.last_updated else "-"
        print(f"  {m.code:>6s} {m.name or '':10s} {(m.sector or ''):20s} "
              f"{m.data_start or '':12s} {m.data_end or '':12s} {m.total_days or 0:>5d} {last_upd}")


def clear_all():
    """清空所有回测缓存"""
    from models import SessionLocal
    from db import clear_backtest_data

    db = SessionLocal()
    try:
        clear_backtest_data(db)
        print("✅ 已清空所有回测缓存")
    finally:
        db.close()


# ═══════════════════════════════════════════════
# 命令行入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    top_n = 5
    days = 365
    manual = []

    args = sys.argv[1:]

    if "--status" in args:
        show_status()
        sys.exit(0)

    if "--clear" in args:
        clear_all()
        sys.exit(0)

    for arg in args:
        if arg.startswith("--top="):
            top_n = int(arg.split("=", 1)[1])
        elif arg.startswith("--days="):
            days = int(arg.split("=", 1)[1])
        elif arg.startswith("--stock="):
            manual.append(arg.split("=", 1)[1])
        elif arg == "--refresh-all":
            top_n = 999  # 取所有板块

    prefetch_all(top_n=top_n, days=days, manual_stocks=manual)
