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

def daily_refresh():
    """每日增量刷新：拉取所有A股最近1天数据，更新到DB"""
    log.info("=== 每日数据增量刷新 ===")
    
    stocks = get_all_stocks()
    if not stocks:
        log.error("获取股票列表失败")
        return {"ok": 0, "failed": 0, "total": 0}
    
    log.info(f"共 {len(stocks)} 只股票")
    
    # 拉取每只股票最近5天（确保覆盖到最近交易日）
    # 只取最新的1条存入DB（upsert）
    ok = 0
    fail = 0
    
    # 先判断今日是否有数据（非交易日的增量是空的）
    today_str = date.today().isoformat()
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(fetch_stock_data, s["code"], s["name"], 5): s for s in stocks}
        
        for i, future in enumerate(as_completed(futures), 1):
            s = futures[future]
            try:
                records = future.result()
                if records:
                    # 只取最新1条（当日数据）
                    latest = records[-1]
                    if latest["date"] == today_str or True:  # 接受最近的数据
                        from models import SessionLocal
                        from db import save_backtest_data_batch
                        db = SessionLocal()
                        try:
                            save_backtest_data_batch(db, s["code"], [latest])
                            # 更新meta
                            from db import save_backtest_meta
                            from models import BacktestStockMeta
                            meta = db.query(BacktestStockMeta).filter(
                                BacktestStockMeta.code == s["code"]
                            ).first()
                            if meta:
                                # 只更新end日期
                                dates = [latest["date"]]
                                if meta.data_end and meta.data_end > latest["date"]:
                                    dates.append(meta.data_end)
                                save_backtest_meta(
                                    db, s["code"], s["name"],
                                    meta.sector or "全A股",
                                    meta.data_start or latest["date"],
                                    max(dates),
                                    (meta.total_days or 0) + 1,
                                )
                            else:
                                save_backtest_meta(
                                    db, s["code"], s["name"], "全A股",
                                    latest["date"], latest["date"], 1,
                                )
                        finally:
                            db.close()
                        ok += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
            
            if i % 500 == 0:
                log.info(f"  进度: {i}/{len(stocks)} | OK={ok} FAIL={fail}")
    
    log.info(f"✅ 增量完成: {ok} 成功 / {fail} 失败")
    return {"ok": ok, "failed": fail, "total": len(stocks)}


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
        daily_refresh()
    else:
        stocks = get_all_stocks()
        if not stocks:
            log.error("无法获取股票列表，退出")
            sys.exit(1)
        batch_run(stocks, days=days, max_workers=max_workers, resume=resume)
