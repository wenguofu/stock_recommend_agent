#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全A股批量数据预取脚本

功能：
  1. 一次性拉取所有A股（~5500只）过去N天数据
  2. 支持断点续传（记录已完成的股票）
  3. 多线程并发 + 限速
  4. 存储到 backtest_data 表

用法：
  uv run python batch_prefetch_all.py                    # 默认365天
  uv run python batch_prefetch_all.py --days=30           # 只拉30天
  uv run python batch_prefetch_all.py --reset             # 清空重来
  uv run python batch_prefetch_all.py --status            # 查看进度
  uv run python batch_prefetch_all.py --resume            # 从上次断点继续
  uv run python batch_prefetch_all.py --daily             # 每日增量模式（只拉最近1天）
"""

import json
import os
import sys
import time
import logging
import traceback
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional

import numpy as np
import pandas as pd
import urllib.request

logging.basicConfig(level=logging.INFO, format="[Batch] %(asctime)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(__file__)
PROGRESS_FILE = os.path.join(PROJECT_DIR, ".batch_prefetch_progress.json")


# ═══════════════════════════════════════════════
# 1. 全市场股票列表
# ═══════════════════════════════════════════════

def get_all_stocks() -> List[Dict]:
    """获取全A股股票列表（akshare优先 → 本地缓存备选）"""
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        stocks = []
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip()
            name = str(row.get("name", "")).strip()
            if code and name and len(code) == 6:
                stocks.append({"code": code, "name": name})
        log.info(f"全市场股票: {len(stocks)} 只(akshare)")
        return stocks
    except Exception as e:
        log.warning(f"akshare获取股票列表失败: {e}")
        # 回退到本地缓存
        cache_file = os.path.join(PROJECT_DIR, "stock_list_cache.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    cache = json.load(f)
                stocks = cache.get("stocks", [])
                log.info(f"全市场股票: {len(stocks)} 只(缓存)")
                return stocks
            except Exception as e2:
                log.error(f"读取缓存也失败: {e2}")
        return []


# ═══════════════════════════════════════════════
# 2. 数据拉取（多源策略）
# ═══════════════════════════════════════════════

def fetch_stock_data(code: str, name: str, days: int = 365) -> List[Dict]:
    """拉取单只股票数据（非交易时段跳过akshare直用Sina），含重试"""
    
    # 判断当前是否为交易时段（akshare东方财富接口非交易时段返回空）
    now = datetime.now()
    is_trading_time = (
        now.weekday() < 5 and (
            (now.hour == 9 and now.minute >= 30) or
            10 <= now.hour <= 11 or
            13 <= now.hour <= 15
        )
    )
    
    # 方案A：akshare（仅交易时段，有换手率）
    if is_trading_time:
        for attempt in range(3):
            try:
                import akshare as ak
                end = date.today()
                start = end - timedelta(days=int(days * 1.5))
                df = ak.stock_zh_a_hist(
                    symbol=code, period="daily",
                    start_date=start.strftime("%Y%m%d"),
                    end_date=end.strftime("%Y%m%d"),
                    adjust="qfq",
                )
                if df is not None and not df.empty:
                    records = _df_to_records(df, days)
                    if records:
                        return records
            except ImportError:
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(1.5)
    
    # 方案B：Sina API（无换手率但有涨跌幅，24小时可用）
    for attempt in range(2):
        try:
            sina_code = f"sh{code}" if code.startswith(("5", "6", "9")) else f"sz{code}"
            url = (f"http://money.finance.sina.com.cn/quotes_service/api/"
                   f"json_v2.php/CN_MarketData.getKLineData?"
                   f"symbol={sina_code}&scale=240&ma=no&datalen={min(days, 1023)}")
            sinareq = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                'Referer': 'http://finance.sina.com.cn',
            })
            req = urllib.request.urlopen(sinareq, timeout=15)
            data = json.loads(req.read().decode())
            if data and isinstance(data, list) and len(data) > 0:
                records = _sina_to_records(data, days)
                if records:
                    return records
        except Exception as e:
            if attempt < 1:
                time.sleep(2)
    
    return []


def _df_to_records(df: pd.DataFrame, days: int) -> List[Dict]:
    """将akshare的DataFrame转为记录列表"""
    col_map = {
        "日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
        "最低": "low", "成交量": "volume", "成交额": "amount",
        "涨跌幅": "change_pct", "换手率": "turnover",
    }
    df = df.rename(columns=col_map)
    records = []
    for _, row in df.iterrows():
        try:
            records.append({
                "code": "",
                "date": str(row["date"])[:10],
                "open": float(row.get("open", 0)),
                "close": float(row.get("close", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "volume": float(row.get("volume", 0)),
                "amount": float(row.get("amount", 0)),
                "change_pct": float(row.get("change_pct", 0)),
                "turnover": float(row.get("turnover", 0)),
                "source": "akshare",
            })
        except (ValueError, TypeError):
            continue
    if len(records) > days:
        records = records[-days:]
    return records


def _sina_to_records(data: List[Dict], days: int) -> List[Dict]:
    """将Sina JSON转为记录列表（计算涨跌幅 + 推算 amount）

    Sina K-line 接口字段: {day, open, high, low, close, volume}
    - volume 单位是「股」(不是手), amount = close × volume
    - turnover 字段 Sina K-line 不返回, 留 0 标记待 enrich_with_tencent_snapshot 回填
    """
    closes = [float(d.get("close", 0)) for d in data]
    records = []
    for i, d in enumerate(data):
        cp = 0.0
        if i > 0 and closes[i - 1] > 0:
            cp = (closes[i] - closes[i - 1]) / closes[i - 1] * 100
        close = closes[i]
        volume = float(d.get("volume", 0))
        # amount 推算: close × volume (volume 单位是股)
        amount = close * volume if close > 0 and volume > 0 else 0.0
        records.append({
            "code": "",
            "date": d.get("day", "")[:10],
            "open": float(d.get("open", 0)),
            "close": close,
            "high": float(d.get("high", 0)),
            "low": float(d.get("low", 0)),
            "volume": volume,
            "amount": amount,
            "change_pct": round(cp, 2),
            "turnover": 0,  # Sina K-line 无换手率, 由腾讯快照二次回填
            "source": "sina-amount-estimated",
        })
    if len(records) > days:
        records = records[-days:]
    return records


def _fetch_tencent_snapshot(code: str) -> Optional[Dict]:
    """从腾讯 qt.gtimg.cn 拉取单只股票当日快照

    返回: {amount_wan(万元), turnover_pct(%), market_cap_yi(亿), circulate_cap_yi(亿)} 或 None
    失败返回 None, 不抛异常.
    """
    sina_code = f'sh{code}' if code.startswith(('5', '6', '9')) else f'sz{code}'
    url = f'https://qt.gtimg.cn/q={sina_code}'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode('gbk', errors='ignore')
    except Exception as e:
        log.debug(f"  腾讯快照 {code} 失败: {e}")
        return None
    try:
        body = raw.split('="', 1)[1].rstrip('";\n')
        parts = body.split('~')
        if len(parts) < 50:
            return None
        return {
            'amount_wan': float(parts[37]),
            'turnover_pct': float(parts[38]),
            'market_cap_yi': float(parts[45]),
            'circulate_cap_yi': float(parts[44]),
        }
    except (ValueError, IndexError) as e:
        log.debug(f"  腾讯快照 {code} 解析失败: {e}")
        return None


def enrich_with_tencent_snapshot(codes: List[str], sleep_sec: float = 0.5) -> int:
    """用腾讯快照二次回填 backtest_data 中 Sina 估算行的 turnover 与 amount

    限流: 单次调用间隔 sleep_sec 秒 (默认 0.5s, 50只/批).
    失败: 单只 code 拉取失败不影响其它 code, 不抛异常.

    Returns: 成功回填的行数.
    """
    from models import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    updated = 0
    try:
        for code in codes:
            snap = _fetch_tencent_snapshot(code)
            if not snap:
                continue
            # 找该 code 最新一天 (replace-mode 保证唯一)
            row = db.execute(text(
                'SELECT date FROM backtest_data WHERE code=:c ORDER BY date DESC LIMIT 1'
            ), {'c': code}).fetchone()
            if not row:
                continue
            latest_date = row[0]
            amount_yuan = snap['amount_wan'] * 1e4
            db.execute(text(
                'UPDATE backtest_data SET amount=:a, turnover=:t '
                'WHERE code=:c AND date=:d'
            ), {'a': amount_yuan, 't': snap['turnover_pct'], 'c': code, 'd': latest_date})
            updated += 1
            time.sleep(sleep_sec)
        db.commit()
    except Exception as e:
        log.warning(f"  enrich_with_tencent_snapshot 异常: {e}")
        db.rollback()
    finally:
        db.close()
    return updated


# ═══════════════════════════════════════════════
# 3. 数据库写入
# ═══════════════════════════════════════════════

def save_stock_batch(code: str, name: str, records: List[Dict]):
    """保存单只股票数据到 DB（替换模式）"""
    if not records:
        return 0
    
    from models import SessionLocal
    from db import save_backtest_data_batch, save_backtest_meta, clear_backtest_data
    
    db = SessionLocal()
    try:
        clear_backtest_data(db, code)
        saved = save_backtest_data_batch(db, code, records)
        dates = [r["date"] for r in records]
        save_backtest_meta(
            db, code, name,
            sector="全A股批量",
            data_start=min(dates), data_end=max(dates),
            total_days=len(records),
        )
        return saved
    except Exception as e:
        log.warning(f"  DB写入异常 {code}: {e}")
        return 0
    finally:
        db.close()


# ═══════════════════════════════════════════════
# 4. 进度管理（断点续传）
# ═══════════════════════════════════════════════

def load_progress() -> Dict:
    """加载进度文件"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"completed": [], "failed": [], "started_at": None, "total": 0}


def save_progress(progress: Dict):
    """保存进度"""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def get_db_completed_with_data_after(min_date: str) -> set:
    """从 DB 读取 data_end >= min_date 的股票代码集合（用于 daily 增量跳过）。

    Returns: set of stock codes whose latest data is at or after min_date.
    """
    from models import SessionLocal, BacktestStockMeta
    session = SessionLocal()
    try:
        rows = session.query(BacktestStockMeta.code).filter(
            BacktestStockMeta.data_end >= min_date
        ).all()
        return {r[0] for r in rows}
    finally:
        session.close()


def get_db_completed() -> set:
    """从数据库获取已完成股票列表"""
    from models import SessionLocal, BacktestStockMeta
    db = SessionLocal()
    try:
        metas = db.query(BacktestStockMeta).all()
        return {m.code for m in metas}
    finally:
        db.close()


# ═══════════════════════════════════════════════
# 5. 工作线程
# ═══════════════════════════════════════════════

def worker_job(code: str, name: str, days: int) -> Dict:
    """单个工人的工作"""
    t0 = time.time()
    
    # 拉取数据
    records = fetch_stock_data(code, name, days)
    if not records:
        return {"code": code, "name": name, "status": "failed", "reason": "数据为空"}
    
    # 写库
    saved = save_stock_batch(code, name, records)
    elapsed = time.time() - t0
    
    return {
        "code": code,
        "name": name,
        "status": "ok" if saved > 0 else "failed",
        "days": len(records),
        "source": records[-1].get("source", "?"),
        "elapsed": round(elapsed, 1),
    }


# ═══════════════════════════════════════════════
# 6. 批量执行
# ═══════════════════════════════════════════════

def batch_run(stocks: List[Dict], days: int = 365, max_workers: int = 8,
              resume: bool = False, daily_mode: bool = False):
    """执行批量拉取"""
    
    total = len(stocks)
    log.info(f"批量开始: {total} 只股票, {days} 天, {max_workers} 线程")
    
    # 加载进度
    completed_codes = set()
    failed_codes = set()
    
    if resume:
        progress = load_progress()
        completed_codes = set(progress.get("completed", []))
        failed_codes = set(progress.get("failed", []))
        log.info(f"断点续传: 已完{len(completed_codes)} 失败{len(failed_codes)}")
    elif daily_mode:
        # 每日模式：只拉未缓存或数据过期的
        db_codes = get_db_completed()
        completed_codes = db_codes
        log.info(f"每日增量: 已有{len(completed_codes)}只缓存")
    
    # 过滤待处理
    pending = []
    for s in stocks:
        if s["code"] not in completed_codes and s["code"] not in failed_codes:
            pending.append(s)
    
    if not pending:
        log.info("所有股票已完成，无需处理")
        return {"ok": len(completed_codes), "failed": len(failed_codes), "total": total}
    
    log.info(f"待处理: {len(pending)}/{total} 只")
    
    # 执行
    ok_count = len(completed_codes)
    fail_count = len(failed_codes)
    t_start = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker_job, s["code"], s["name"], days): s for s in pending}
        
        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            code = result["code"]
            name = result["name"]
            
            if result["status"] == "ok":
                ok_count += 1
                src = result.get("source", "?")
                dy = result.get("days", 0)
                et = result.get("elapsed", 0)
                log.info(f"[{ok_count}/{total}] ✅ {name}({code}) {dy}d/{src} {et}s")
            else:
                fail_count += 1
                log.warning(f"[{ok_count+fail_count}/{total}] ❌ {name}({code}) {result.get('reason','?')}")
            
            # 每10只保存一次进度
            if i % 10 == 0:
                elapsed = time.time() - t_start
                rate = i / elapsed * 60
                remain = len(pending) - i
                eta_min = remain / rate if rate > 0 else 999
                log.info(f"进度: {ok_count}/{total} ✅ / {fail_count} ❌ | "
                         f"{rate:.0f}只/分 | 剩余≈{eta_min:.0f}分钟")
                save_progress({
                    "completed": list(get_db_completed()),
                    "failed": [],
                    "started_at": datetime.now().isoformat(),
                    "total": total,
                })
    
    elapsed = time.time() - t_start
    log.info(f"✅ 批量完成: {ok_count} 成功 / {fail_count} 失败 / {total} 总计")
    log.info(f"   耗时: {elapsed:.0f}秒 ({elapsed/60:.1f}分钟)")

    # 腾讯快照二次回填 turnover + 校验 amount (Sina 估算行)
    try:
        all_codes = [s['code'] for s in stocks]
        enriched = enrich_with_tencent_snapshot(all_codes)
        log.info(f"   腾讯快照二次回填: {enriched}/{len(all_codes)} 只")
    except Exception as e:
        log.warning(f"   腾讯快照回填异常: {e}")

    save_progress({
        "completed": list(get_db_completed()),
        "failed": [],
        "started_at": datetime.now().isoformat(),
        "total": total,
    })

    return {"ok": ok_count, "failed": fail_count, "total": total}


# ═══════════════════════════════════════════════
# 7. 每日增量（供定时任务调用）
# ═══════════════════════════════════════════════

def daily_refresh(resume: bool = True, max_workers: int = 12, max_minutes: int = 8):
    """每日增量刷新：拉取所有A股最近1天数据，更新到DB。

    与原版的区别（修复 daily_kline_data_lag bug）：
    1. 复用 batch_run 的 progress 持久化：每次运行只处理未完成的股票
    2. 跳过 data_end >= today_minus_1 的股票（已被最近一次刷新覆盖的）
    3. 默认 max_workers=12（原 6）以匹配现代 CPU
    4. 每 100 只保存进度，断点续传
    5. soft-timeout 在 max_minutes 后停止调度新任务（已提交的等待完成）
    """
    log.info("=== 每日数据增量刷新（断点续传 + 跳过已更新） ===")

    stocks = get_all_stocks()
    if not stocks:
        log.error("获取股票列表失败")
        return {"ok": 0, "failed": 0, "total": 0}

    today_str = date.today().isoformat()
    # 跳过阈值放宽到最近 7 天（覆盖周末 + 节假日），否则周末/节后第一天
    # 跑 daily_refresh 时 yestrday_str 会是周六/周日，Sina API 只返回到
    # 上一个交易日，导致最新数据被误判为"远期"而失败。
    skip_threshold_str = (date.today() - timedelta(days=7)).isoformat()
    log.info(f"今天: {today_str}, 跳过阈值: data_end >= {skip_threshold_str} (覆盖周末/节假日)")

    # ── 增量过滤 ──
    # 1) DB 已有当天/昨天的 → 视为已完成
    # 2) 加载上次进度 → 已完成/已失败的也不重跑
    db_completed = get_db_completed_with_data_after(skip_threshold_str)
    log.info(f"DB 中 data_end >= {skip_threshold_str} 的: {len(db_completed)} 只")

    progress = load_progress() if resume else {"completed": [], "failed": []}
    completed_set = set(progress.get("completed", [])) | db_completed
    failed_set = set(progress.get("failed", []))

    pending = [
        s for s in stocks
        if s["code"] not in completed_set and s["code"] not in failed_set
    ]
    log.info(
        f"待处理: {len(pending)}/{len(stocks)} (跳过已完成 {len(completed_set)}, 失败 {len(failed_set)})"
    )

    if not pending:
        log.info("✅ 所有股票已是最新，无需处理")
        return {"ok": len(completed_set), "failed": len(failed_set), "total": len(stocks)}

    # ── 并发抓取 + 写入 ──
    ok = len(completed_set)
    fail = len(failed_set)
    newly_completed: List[str] = []
    newly_failed: List[str] = []
    t_start = time.time()
    soft_timeout = max_minutes * 60

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_stock_data, s["code"], s["name"], 5): s
                   for s in pending}

        try:
            for i, future in enumerate(as_completed(futures), 1):
                # soft-timeout: 不再调度新的等待，但让已提交的完成
                if time.time() - t_start > soft_timeout:
                    log.warning(
                        f"⏰ 软超时 ({max_minutes} 分钟): 已处理 {i}/{len(pending)}; "
                        f"剩余 {len(pending) - i} 只留待下次运行"
                    )
                    break

                s = futures[future]
                try:
                    records = future.result()
                    if records:
                        latest = records[-1]
                        # 接受最近 2 天的数据（节假日后回填）
                        # 接受 last 7 天的数据（覆盖周末/节假日）
                        if latest["date"] >= skip_threshold_str:
                            from models import SessionLocal
                            from db import save_backtest_data_batch, save_backtest_meta
                            from models import BacktestStockMeta
                            session = SessionLocal()
                            try:
                                # 修复 daily_kline_gap bug：保存全部 fetch 的记录，
                                # 不只是 latest一条。否则中间日期会永远丢失，gap累积。
                                save_backtest_data_batch(session, s["code"], records)
                                meta = session.query(BacktestStockMeta).filter(
                                    BacktestStockMeta.code == s["code"]
                                ).first()
                                if meta:
                                    new_start = min(meta.data_start or records[0]["date"],
                                                    records[0]["date"])
                                    new_end = max(meta.data_end or latest["date"],
                                                  latest["date"])
                                    save_backtest_meta(
                                        session, s["code"], s["name"],
                                        meta.sector or "全A股",
                                        new_start,
                                        new_end,
                                        # 实际行数（save_backtest_data_batch 已 upsert，
                                        # 重复日期不计；这里给个保守估算避免大跳动）
                                        (meta.total_days or 0) + len(records),
                                    )
                                else:
                                    save_backtest_meta(
                                        session, s["code"], s["name"], "全A股",
                                        records[0]["date"],
                                        records[-1]["date"],
                                        len(records),
                                    )
                                newly_completed.append(s["code"])
                                ok += 1
                            finally:
                                session.close()
                        else:
                            # 远期数据（> 昨天）—— 不更新本次，但标记为失败以便下次重试
                            newly_failed.append(s["code"])
                            fail += 1
                    else:
                        newly_failed.append(s["code"])
                        fail += 1
                except Exception as e:
                    log.warning(f"  ❌ {s['code']} {s.get('name','')}: {e}")
                    newly_failed.append(s["code"])
                    fail += 1

                # 每 100 只持久化一次进度（断点续传）
                if i % 100 == 0:
                    save_progress({
                        "completed": list(completed_set) + newly_completed,
                        "failed": list(failed_set) + newly_failed,
                        "started_at": datetime.now().isoformat(),
                        "total": len(stocks),
                    })
                    elapsed = time.time() - t_start
                    rate = i / elapsed * 60 if elapsed > 0 else 0
                    log.info(
                        f"  📊 进度: {i}/{len(pending)} | OK={len(newly_completed)} "
                        f"FAIL={len(newly_failed)} | {rate:.0f}只/min"
                    )
        finally:
            # 退出前（无论超时或完成）保存进度
            save_progress({
                "completed": list(completed_set) + newly_completed,
                "failed": list(failed_set) + newly_failed,
                "started_at": datetime.now().isoformat(),
                "total": len(stocks),
            })

    elapsed = time.time() - t_start
    log.info(
        f"✅ 本次刷新: 新增 OK={len(newly_completed)} FAIL={len(newly_failed)} "
        f"| 累计 OK={ok} FAIL={fail} | 耗时 {elapsed:.0f}s"
    )
    return {"ok": ok, "failed": fail, "total": len(stocks),
            "newly_ok": len(newly_completed), "newly_failed": len(newly_failed)}


# ═══════════════════════════════════════════════
# 命令行入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    days = 365
    max_workers = 8
    resume = False
    daily_mode = False
    
    args = sys.argv[1:]
    
    for arg in args:
        if arg == "--status":
            from models import SessionLocal, BacktestStockMeta
            db = SessionLocal()
            try:
                total = db.query(BacktestStockMeta).count()
                total_rows = db.query(__import__('models', fromlist=['BacktestData']).BacktestData).count()
                log.info(f"📊 DB状态: {total} 只股票, {total_rows} 条日K线")
                if total > 0:
                    sample = db.query(BacktestStockMeta).order_by(
                        BacktestStockMeta.last_updated.desc()
                    ).first()
                    log.info(f"   最新更新: {sample.code} {sample.name} ({sample.data_end})")
            finally:
                db.close()
            sys.exit(0)
        
        if arg == "--reset":
            from models import SessionLocal
            from db import clear_backtest_data
            db = SessionLocal()
            clear_backtest_data(db)
            db.close()
            if os.path.exists(PROGRESS_FILE):
                os.remove(PROGRESS_FILE)
            log.info("已清空所有回测缓存")
            sys.exit(0)
        
        if arg == "--daily":
            daily_mode = True
        if arg == "--resume":
            resume = True
        if arg.startswith("--days="):
            days = int(arg.split("=", 1)[1])
        if arg.startswith("--workers="):
            max_workers = int(arg.split("=", 1)[1])
    
    if daily_mode:
        daily_refresh(resume=resume)
    else:
        stocks = get_all_stocks()
        if not stocks:
            log.error("无法获取股票列表，退出")
            sys.exit(1)
        batch_run(stocks, days=days, max_workers=max_workers, resume=resume)
