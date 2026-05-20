#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
历史回测引擎 v1 — 验证4大策略（板块动量/游资/量化/基础工具）的历史表现

核心思路：
  针对历史每一天，用当天可获取的数据模拟策略评分，
  然后跟踪评分后的 N 日涨跌幅，看策略信号是否拟合实际走势。

用法：
  uv run python strategy_backtest.py 000001        # 回测单股所有策略
  uv run python strategy_backtest.py 000001 youzi  # 回测指定策略
  uv run python strategy_backtest.py 000001 --optimize  # 参数优化
"""

import json
import math
import os
import sys
import time
import traceback
from collections import defaultdict
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Any

import numpy as np
import pandas as pd

PROJECT_DIR = os.path.dirname(__file__)
REPORT_DIR = os.path.join(os.path.dirname(__file__), "eval_result")
BACKTEST_DIR = os.path.join(PROJECT_DIR, "backtest_results")
os.makedirs(BACKTEST_DIR, exist_ok=True)

# ═══════════════════════════════════════════════
# 策略配置（与 strategy_engine.py 保持一致）
# ═══════════════════════════════════════════════

STRATEGIES = {
    "sector_momentum": {
        "name": "板块动量",
        "desc": "当日最强板块的领涨股",
        "min_score": 30,
    },
    "youzi": {
        "name": "游资策略",
        "desc": "高换手、强动量短线机会",
        "min_score": 25,
    },
    "lianghua": {
        "name": "量化策略",
        "desc": "MACD金叉、放量突破技术型",
        "min_score": 20,
    },
    "jichang": {
        "name": "基础工具",
        "desc": "基本面+技术面稳健型",
        "min_score": 15,
    },
}

# ═══════════════════════════════════════════════
# 1. 历史数据获取（含换手率）
# ═══════════════════════════════════════════════

# 数据缓存（同股票只拉一次，所有策略共享）
_BACKTEST_DATA_CACHE = {}  # code -> DataFrame

# ═══════════════════════════════════════════════
# 数据库缓存（优先于API，持久化存储）
# ═══════════════════════════════════════════════

def _load_from_db(code: str, days: int = 720) -> Optional[pd.DataFrame]:
    """从 backtest_data 表加载缓存数据"""
    try:
        from models import SessionLocal
        from db import get_backtest_data
        db = SessionLocal()
        try:
            records = get_backtest_data(db, code)
        finally:
            db.close()
        
        if not records:
            return None
        
        # 检查是否够用
        if len(records) < days * 0.5:
            return None
        
        # 检查是否最新（最近一次交易日）
        latest_date = records[-1]["date"]
        today_str = date.today().isoformat()
        days_diff = (pd.Timestamp(today_str) - pd.Timestamp(latest_date)).days
        if days_diff > 10:
            # 数据超过10天未更新，视为过期
            return None
        
        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 截取
        if len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        
        print(f"[Backtest] DB缓存命中 {code}: {len(df)} 天 (换手率={'有' if df.iloc[-1].get('turnover', 0) > 0 else '无'})")
        return df
    except Exception as e:
        print(f"[Backtest] DB缓存读取异常: {e}")
        return None


def _save_to_db(code: str, df: pd.DataFrame, source: str = "akshare"):
    """将拉取的数据存入 backtest_data 表（异步，不阻塞）"""
    try:
        from models import SessionLocal
        from db import save_backtest_data_batch, save_backtest_meta
        db = SessionLocal()
        try:
            records = []
            for _, row in df.iterrows():
                records.append({
                    "date": str(row["date"])[:10],
                    "open": float(row.get("open", 0)),
                    "close": float(row.get("close", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "volume": float(row.get("volume", 0)),
                    "amount": float(row.get("amount", 0)),
                    "change_pct": float(row.get("change_pct", 0)),
                    "turnover": float(row.get("turnover", 0)),
                    "source": source,
                })
            saved = save_backtest_data_batch(db, code, records)
            dates = [r["date"] for r in records]
            save_backtest_meta(
                db, code, name=_guess_stock_name(code),
                sector="回测自动缓存",
                data_start=min(dates), data_end=max(dates),
                total_days=len(records),
            )
        finally:
            db.close()
        print(f"[Backtest] 写入DB缓存 {code}: {saved} 条")
    except Exception as e:
        print(f"[Backtest] 写入DB缓存失败: {e}")


def fetch_historical_daily(code: str, days: int = 720) -> pd.DataFrame:
    """获取股票历史日K线（含换手率），优先走DB缓存 → akshare → Sina"""
    
    # 0. 模块级缓存
    cache_key = f"{code}_{days}"
    if cache_key in _BACKTEST_DATA_CACHE:
        df = _BACKTEST_DATA_CACHE[cache_key]
        print(f"[Backtest] 内存缓存命中 {code}: {len(df)} 天")
        return df
    
    # 1. 数据库持久缓存
    db_df = _load_from_db(code, days)
    if db_df is not None:
        _BACKTEST_DATA_CACHE[cache_key] = db_df
        return db_df
    
    # 2. akshare 实时拉取
    akshare_success = False
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
            col_map = {
                "日期": "date", "开盘": "open", "收盘": "close",
                "最高": "high", "最低": "low", "成交量": "volume",
                "成交额": "amount", "振幅": "amplitude",
                "涨跌幅": "change_pct", "涨跌额": "change_amount",
                "换手率": "turnover",
            }
            df = df.rename(columns=col_map)
            keep = ["date", "open", "close", "high", "low", "volume",
                    "amount", "amplitude", "change_pct", "turnover"]
            for col in keep:
                if col not in df.columns: df[col] = 0.0
            df = df[[c for c in keep if c in df.columns]]
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date").reset_index(drop=True)
            if len(df) > days:
                df = df.tail(days).reset_index(drop=True)
            
            print(f"[Backtest] akshare 获取 {code}: {len(df)} 天 (含换手率)")
            _BACKTEST_DATA_CACHE[cache_key] = df
            
            # 异步存DB
            _save_to_db(code, df, "akshare")
            return df
        else:
            print(f"[Backtest] akshare 无数据")
    except ImportError:
        print(f"[Backtest] akshare 未安装")
    except Exception as e:
        print(f"[Backtest] akshare 异常: {e}")
    
    # 3. Sina 直连备选
    df = _fallback_to_sina(code, days)
    if df is not None and not df.empty:
        _BACKTEST_DATA_CACHE[cache_key] = df
        _save_to_db(code, df, "sina")
    return df


def _fallback_to_sina(code: str, days: int = 720) -> pd.DataFrame:
    """备选：直接用 urllib 调用 Sina API（跳过 DB 缓存防过期）"""
    try:
        import urllib.request
        import json
        
        # 直接用 API 拉取（不走 data_fetchers 的缓存）
        sina_code = f"sh{code}" if code.startswith(("5", "6", "9")) else f"sz{code}"
        url = ("http://money.finance.sina.com.cn/quotes_service/api/"
               f"json_v2.php/CN_MarketData.getKLineData?"
               f"symbol={sina_code}&scale=240&ma=no&datalen={min(days, 1023)}")
        
        req = urllib.request.urlopen(url, timeout=15)
        data = json.loads(req.read().decode())
        
        if not data or not isinstance(data, list):
            return pd.DataFrame()
        
        rows = []
        for d in data:
            rows.append({
                "date": d.get("day", ""),
                "open": float(d.get("open", 0)),
                "close": float(d.get("close", 0)),
                "high": float(d.get("high", 0)),
                "low": float(d.get("low", 0)),
                "volume": float(d.get("volume", 0)),
            })
        
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        
        # 计算涨跌幅
        closes = df["close"].values
        change_pcts = np.full(len(closes), 0.0)
        for i in range(1, len(closes)):
            if closes[i-1] > 0:
                change_pcts[i] = (closes[i] - closes[i-1]) / closes[i-1] * 100
        df["change_pct"] = change_pcts
        df["turnover"] = 0.0
        
        # 用volume估算换手（相对量）
        volume = df["volume"].values
        vol_ma5 = pd.Series(volume).rolling(5).mean().fillna(1)
        df["turnover_est"] = (volume / vol_ma5 * 5).values
        
        print(f"[Backtest] Sina直连 {code}: {len(df)} 天")
        return df
    except Exception as e:
        print(f"[Backtest] Sina直连也失败: {e}")
        return pd.DataFrame()


def get_pe_estimate(code: str) -> float:
    """获取最新PE（回测时统一用最新值作为近似）"""
    try:
        from data_fetchers import get_fundamental_data
        # 静默尝试，不要打印错误信息
        import logging
        logging.getLogger().disabled = True
        fd = get_fundamental_data(code)
        logging.getLogger().disabled = False
        if fd:
            pe = fd.get("pe_ttm") or fd.get("pe") or fd.get("市盈率", 0)
            if pe and float(pe) > 0:
                return float(pe)
    except:
        pass
    return 30  # 默认PE


# ═══════════════════════════════════════════════
# 2. 历史评分（模拟策略在当天的判断）
# ═══════════════════════════════════════════════

def score_historical(row: pd.Series, strategy: str, pe: float = 30) -> float:
    """
    用历史某一天的数据模拟策略评分
    与 strategy_engine.score_by_strategy() 逻辑一致
    """
    cp = float(row.get("change_pct", 0))
    to = float(row.get("turnover", 0))
    close = float(row.get("close", 0))
    open_p = float(row.get("open", 0))
    
    score = 0.0
    
    # 停牌/低价股过滤
    if close <= 0 or close < 2:
        return -1
    
    # 板块热度不可用（历史无法实时获取），设为中等偏上
    # 如果回测数据有 turnvoer_est（Sina备选），用它替代
    if "turnover_est" in row.index:
        to = float(row.get("turnover_est", to))
    
    # ⚠️ 历史回测中 sector_heat = 0
    # 这意味着 sector_momentum 策略在历史回测中可能比实盘低估
    # 这是保守估计——实际板块热点会带来额外加分
    sector_heat = 0
    
    # ── 通用因子 ──
    if cp >= 9.5:
        score += 10  # 涨停粗略加分
    elif cp >= 5:
        score += 5
    
    if to >= 10:
        score += 8
    elif to >= 5:
        score += 4
    
    # ── 策略特有因子 ──
    if strategy == "sector_momentum":
        if cp >= 9.5: score += 25
        elif cp >= 7: score += 20
        elif cp >= 5: score += 15
        elif cp >= 3: score += 8
        
        if to >= 15: score += 20
        elif to >= 8: score += 12
        elif to >= 3: score += 6
        
        if cp > 0 and to > 3: score += 10
    
    elif strategy == "youzi":
        if cp >= 9.5 and to >= 5: score += 30
        elif cp >= 5: score += 20
        elif cp >= 3: score += 10
        
        if to >= 10: score += 20
        elif to >= 5: score += 12
        elif to >= 3: score += 6
        
        if close > open_p: score += 8
        if cp < 1 or cp > 10: score -= 5
    
    elif strategy == "lianghua":
        if 1 <= cp <= 5: score += 20
        if 3 <= to <= 15: score += 15
        if close > open_p: score += 10
        if 1 < cp < 10 and to > 2: score += 10
    
    elif strategy == "jichang":
        if 0 < cp <= 5: score += 20
        if 2 <= to <= 10: score += 15
        if close > open_p: score += 8
        if 0 < pe < 50: score += 8
        elif 50 <= pe < 100: score += 3
    
    return score


# ═══════════════════════════════════════════════
# 3. 回测执行
# ═══════════════════════════════════════════════

def backtest_strategy(
    code: str,
    strategy: str,
    start_date: str = None,
    end_date: str = None,
    min_score: int = None,
    forward_days: int = 5,
    top_pct: float = None,
    days: int = 720,
) -> Dict[str, Any]:
    """
    回测单策略在某股上的历史表现
    
    Args:
        code: 股票代码
        strategy: 策略名 (sector_momentum|youzi|lianghua|jichang)
        start_date: 回测开始 YYYY-MM-DD
        end_date: 回测结束 YYYY-MM-DD
        min_score: 触发买入的最低评分（覆盖策略默认值）
        forward_days: 买入后跟踪多少天
        top_pct: 若设此值，只取评分最高的 top_pct% 信号
        days: 获取多少天历史数据
    
    Returns:
        dict with: signals, trades, metrics, equity_curve
    """
    strategy_config = STRATEGIES.get(strategy)
    if not strategy_config:
        return {"success": False, "error": f"未知策略: {strategy}"}
    
    min_score_val = min_score if min_score is not None else strategy_config["min_score"]
    
    # 1. 获取数据
    df = fetch_historical_daily(code, days=days)
    if df.empty or len(df) < 10:
        return {"success": False, "error": f"数据不足 (got {len(df)} days)"}
    
    # 2. 过滤日期
    if start_date:
        df = df[df["date"] >= pd.Timestamp(start_date)]
    if end_date:
        df = df[df["date"] <= pd.Timestamp(end_date)]
    if len(df) < 10:
        return {"success": False, "error": f"日期范围内数据不足 (got {len(df)} days)"}
    
    df = df.reset_index(drop=True)
    
    # 3. 获取PE（用于jichang策略）
    pe = get_pe_estimate(code)
    
    # 4. 逐日评分
    scores = []
    for i in range(len(df)):
        row = df.iloc[i]
        s = score_historical(row, strategy, pe)
        scores.append(s)
    
    df["score"] = scores
    
    # 5. 生成信号
    # 信号规则：当日评分 >= min_score → 视为"策略认为该买"的信号
    # 如果设了top_pct，只保留评分最高的那些
    
    df["signal"] = (df["score"] >= min_score_val).astype(int)
    
    if top_pct and top_pct < 100:
        threshold = df[df["signal"] == 1]["score"].quantile(1 - top_pct / 100)
        df["signal"] = ((df["signal"] == 1) & (df["score"] >= threshold)).astype(int)
    
    has_signals = df["signal"].sum() > 0
    
    # 6. 计算未来N日收益
    closes = df["close"].values
    
    for fd in [1, 3, 5, 10, 20]:
        forward_returns = np.full(len(df), np.nan)
        for i in range(len(df) - fd):
            if closes[i] > 0:
                forward_returns[i] = (closes[i + fd] - closes[i]) / closes[i] * 100
        df[f"return_{fd}d"] = forward_returns
    
    # 7. 模拟交易
    # 简单模式：每天只要出信号就买入（如果没持仓），持有 forward_days 天后卖出
    trades = []
    position = 0  # 0=空仓, 1=持仓
    entry_idx = -1
    entry_price = 0
    entry_date = None
    
    for i in range(len(df)):
        if position == 0 and df.iloc[i]["signal"] == 1:
            # 买入
            position = 1
            entry_idx = i
            entry_price = df.iloc[i]["close"]
            entry_date = str(df.iloc[i]["date"])[:10]
        
        elif position == 1 and (i - entry_idx) >= forward_days:
            # 到持有期卖出
            exit_price = df.iloc[i]["close"]
            exit_date = str(df.iloc[i]["date"])[:10]
            pnl_pct = (exit_price - entry_price) / entry_price * 100
            
            # 期间最高/最低
            slice_high = df.iloc[entry_idx:i+1]["high"].max()
            slice_low = df.iloc[entry_idx:i+1]["low"].min()
            
            trades.append({
                "entry_date": entry_date,
                "exit_date": exit_date,
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "hold_days": i - entry_idx,
                "pnl_pct": round(pnl_pct, 2),
                "max_rise": round((slice_high - entry_price) / entry_price * 100, 2),
                "max_fall": round((slice_low - entry_price) / entry_price * 100, 2),
                "entry_score": round(float(df.iloc[entry_idx]["score"]), 1),
                "is_win": pnl_pct > 0,
            } | {
                f"return_{fd}d": round(float(df.iloc[entry_idx][f"return_{fd}d"]), 2)
                for fd in [1, 3, 5, 10, 20]
            })
            
            position = 0
    
    # 8. 计算回测指标
    metrics = compute_backtest_metrics(df, trades, code, strategy)
    
    # 9. 信号质量分析
    signal_quality = analyze_signal_quality(df)
    
    # 10. 信号走势图（每个信号出现时的后续走势）
    signal_profiles = extract_signal_profiles(df, forward_days)
    
    return {
        "success": True,
        "code": code,
        "strategy": strategy,
        "strategy_name": strategy_config["name"],
        "params": {
            "min_score": min_score_val,
            "forward_days": forward_days,
            "period": f"{start_date or 'auto'} ~ {end_date or 'auto'}",
            "top_pct": top_pct,
        },
        "period": {
            "start": str(df["date"].iloc[0])[:10],
            "end": str(df["date"].iloc[-1])[:10],
            "trading_days": len(df),
        },
        "signals": {
            "total_days": int(df["signal"].sum()),
            "signal_density": round(float(df["signal"].mean() * 100), 2),
            "avg_score": round(float(df[df["signal"] == 1]["score"].mean()), 1) if has_signals else 0,
            "score_distribution": {
                ">=50": int((df["score"] >= 50).sum()),
                "30-50": int(((df["score"] >= 30) & (df["score"] < 50)).sum()),
                "15-30": int(((df["score"] >= 15) & (df["score"] < 30)).sum()),
                "<15": int((df["score"] < 15).sum()),
            },
        },
        "trades": trades,
        "metrics": metrics,
        "signal_quality": signal_quality,
        "signal_profiles": signal_profiles,
        "pe_used": pe,
    }


# ═══════════════════════════════════════════════
# 4. 回测指标计算
# ═══════════════════════════════════════════════

def compute_backtest_metrics(
    df: pd.DataFrame, trades: List[Dict], code: str, strategy: str
) -> Dict[str, Any]:
    """计算回测核心指标"""
    
    if not trades:
        return {
            "total_trades": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
            "total_return_compound": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "avg_hold_days": 0,
            "max_consecutive_wins": 0,
            "max_consecutive_losses": 0,
            "profit_factor": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "buy_hold_return": round(
                (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0] * 100, 2
            ) if len(df) >= 2 else 0,
        }
    
    pnls = [t["pnl_pct"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    
    win_count = len(wins)
    loss_count = len(losses)
    total_trades = len(trades)
    win_rate = win_count / total_trades * 100 if total_trades > 0 else 0
    
    total_return = sum(pnls)
    avg_return = total_return / total_trades if total_trades > 0 else 0
    
    # 复利总收益（每次全仓，正确计算资金曲线）
    total_return_compound = (np.prod([1 + p / 100 for p in pnls]) - 1) * 100 if pnls else 0
    
    best_trade = max(pnls) if pnls else 0
    worst_trade = min(pnls) if pnls else 0
    
    # 连胜/连败
    max_cw = 0
    max_cl = 0
    current_streak = 0
    current_type = None  # 'win' or 'loss'
    for t in trades:
        if t["is_win"]:
            if current_type == "win":
                current_streak += 1
            else:
                current_streak = 1
                current_type = "win"
            max_cw = max(max_cw, current_streak)
        else:
            if current_type == "loss":
                current_streak += 1
            else:
                current_streak = 1
                current_type = "loss"
            max_cl = max(max_cl, current_streak)
    
    # 盈亏比
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0
    profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else float("inf") if wins else 0
    
    avg_hold = sum(t["hold_days"] for t in trades) / total_trades if total_trades > 0 else 0
    
    # 基准（买入持有）
    buy_hold = (
        (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0] * 100
        if len(df) >= 2 else 0
    )
    
    # 夏普（基于交易收益）
    if len(pnls) >= 2 and np.std(pnls) > 0:
        sharpe = np.mean(pnls) / np.std(pnls) * np.sqrt(252 / avg_hold) if avg_hold > 0 else 0
    else:
        sharpe = 0
    
    return {
        "total_trades": total_trades,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": round(win_rate, 2),
        "avg_return": round(avg_return, 2),
        "total_return": round(total_return, 2),
        "total_return_compound": round(total_return_compound, 2),
        "best_trade": round(best_trade, 2),
        "worst_trade": round(worst_trade, 2),
        "avg_hold_days": round(avg_hold, 1),
        "max_consecutive_wins": max_cw,
        "max_consecutive_losses": max_cl,
        "profit_factor": round(profit_factor, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "sharpe_ratio": round(sharpe, 2),
        "buy_hold_return": round(buy_hold, 2),
        "excess_return": round(total_return - buy_hold, 2),
        "excess_compound_return": round(total_return_compound - buy_hold, 2),
    }


def analyze_signal_quality(df: pd.DataFrame) -> Dict[str, Any]:
    """分析信号质量：信号出现后各周期涨跌分布"""
    signal_rows = df[df["signal"] == 1]
    if len(signal_rows) == 0:
        return {"error": "无信号"}
    
    quality = {}
    for fd in [1, 3, 5, 10, 20]:
        ret_col = f"return_{fd}d"
        valid = signal_rows[ret_col].dropna()
        if len(valid) == 0:
            continue
        
        positive_rate = (valid > 0).sum() / len(valid) * 100
        quality[f"{fd}d"] = {
            "samples": int(len(valid)),
            "positive_rate": round(positive_rate, 2),
            "avg_return": round(float(valid.mean()), 2),
            "median_return": round(float(valid.median()), 2),
            "std": round(float(valid.std()), 2),
            "max": round(float(valid.max()), 2),
            "min": round(float(valid.min()), 2),
        }
    
    return quality


def extract_signal_profiles(df: pd.DataFrame, forward_days: int = 10) -> List[Dict]:
    """提取每个信号出现后N天的走势剖面"""
    profiles = []
    signal_indices = df[df["signal"] == 1].index.tolist()
    
    for idx in signal_indices[:20]:  # 只取前20个信号，防止太长
        row = df.iloc[idx]
        profile = {
            "date": str(row["date"])[:10],
            "price": float(row["close"]),
            "score": float(row["score"]),
            "change_pct": float(row["change_pct"]),
            "turnover": float(row["turnover"]),
        }
        
        future = []
        for offset in range(1, forward_days + 1):
            if idx + offset < len(df):
                future_row = df.iloc[idx + offset]
                future.append({
                    "offset": offset,
                    "date": str(future_row["date"])[:10],
                    "price": float(future_row["close"]),
                    "return_pct": round(
                        (future_row["close"] - row["close"]) / row["close"] * 100, 2
                    ),
                })
        
        profile["future"] = future
        profiles.append(profile)
    
    return profiles


# ═══════════════════════════════════════════════
# 5. 多策略对比
# ═══════════════════════════════════════════════

def backtest_all_strategies(
    code: str,
    start_date: str = None,
    end_date: str = None,
    forward_days: int = 5,
    days: int = 720,
) -> Dict[str, Any]:
    """回测某股上所有4个策略，返回对比结果"""
    results = {}
    
    for key in STRATEGIES:
        try:
            bt = backtest_strategy(
                code=code,
                strategy=key,
                start_date=start_date,
                end_date=end_date,
                forward_days=forward_days,
                days=days,
            )
            results[key] = {
                "strategy_name": STRATEGIES[key]["name"],
                "success": bt["success"],
                "metrics": bt.get("metrics", {}),
                "signals": bt.get("signals", {}),
                "trade_count": len(bt.get("trades", [])),
            }
            if bt.get("error"):
                results[key]["error"] = bt["error"]
        except Exception as e:
            results[key] = {
                "strategy_name": STRATEGIES[key]["name"],
                "success": False,
                "error": str(e),
            }
    
    return {
        "success": True,
        "code": code,
        "stock_name": _guess_stock_name(code),
        "period": {
            "start": start_date or "auto",
            "end": end_date or "auto",
        },
        "strategies": results,
        "generated_at": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════
# 6. 策略优化（参数搜索）
# ═══════════════════════════════════════════════

def optimize_strategy(
    code: str,
    strategy: str,
    param_name: str = "min_score",
    param_values: List[int] = None,
    forward_days: int = 5,
    days: int = 720,
    metric: str = "win_rate",
) -> Dict[str, Any]:
    """
    策略参数优化
    
    Args:
        code: 股票代码
        strategy: 策略名
        param_name: 优化参数名 (默认 min_score)
        param_values: 要测试的参数值列表
        forward_days: 持仓天数
        days: 历史数据天数
        metric: 优化目标的指标名 (win_rate, total_return, sharpe_ratio, profit_factor)
    """
    if param_values is None:
        param_values = [10, 15, 20, 25, 30, 35, 40, 45, 50]
    
    results = []
    for val in param_values:
        bt = backtest_strategy(
            code=code,
            strategy=strategy,
            min_score=val,
            forward_days=forward_days,
            days=days,
        )
        if bt["success"]:
            results.append({
                param_name: val,
                "total_trades": bt["metrics"]["total_trades"],
                "win_rate": bt["metrics"]["win_rate"],
                "avg_return": bt["metrics"]["avg_return"],
                "total_return": bt["metrics"]["total_return"],
                "total_return_compound": bt["metrics"]["total_return_compound"],
                "sharpe_ratio": bt["metrics"]["sharpe_ratio"],
                "profit_factor": bt["metrics"]["profit_factor"],
                "best_trade": bt["metrics"]["best_trade"],
                "worst_trade": bt["metrics"]["worst_trade"],
                "max_consecutive_wins": bt["metrics"]["max_consecutive_wins"],
                "max_consecutive_losses": bt["metrics"]["max_consecutive_losses"],
            })
    
    # 按指定指标排序
    metric_key = metric
    results.sort(key=lambda x: x.get(metric_key, 0), reverse=True)
    
    # 排名
    for i, r in enumerate(results):
        r["rank"] = i + 1
    
    return {
        "success": True,
        "code": code,
        "strategy": strategy,
        "strategy_name": STRATEGIES.get(strategy, {}).get("name", strategy),
        "optimized_param": param_name,
        "optimization_metric": metric,
        "forward_days": forward_days,
        "results": results,
        "best": results[0] if results else None,
        "worst": results[-1] if results else None,
        "generated_at": datetime.now().isoformat(),
    }


# ═══════════════════════════════════════════════
# 7. 格式化输出
# ═══════════════════════════════════════════════

def format_backtest_report(bt_result: Dict) -> str:
    """格式化单策略回测报告"""
    if not bt_result.get("success"):
        return f"❌ 回测失败: {bt_result.get('error', '未知')}"
    
    lines = []
    lines.append(f"## 📊 策略回测报告")
    lines.append(f"")
    lines.append(f"**股票**: {bt_result['code']}")
    lines.append(f"**策略**: {bt_result['strategy_name']} ({bt_result['strategy']})")
    lines.append(f"**回测区间**: {bt_result['period']['start']} ~ {bt_result['period']['end']} ({bt_result['period']['trading_days']}个交易日)")
    lines.append(f"**持仓天数**: {bt_result['params']['forward_days']}天")
    lines.append(f"**触发评分**: ≥{bt_result['params']['min_score']}")
    lines.append(f"")
    
    # 信号统计
    sig = bt_result["signals"]
    lines.append(f"### 📈 信号分布")
    lines.append(f"| 范围 | 天数 |")
    lines.append(f"|------|------|")
    for k, v in sig["score_distribution"].items():
        lines.append(f"| {k} | {v}天 |")
    lines.append(f"| **信号总天数** | **{sig['total_days']}天** ({sig['signal_density']}%) |")
    lines.append(f"| **平均信号评分** | **{sig['avg_score']}** |")
    lines.append(f"")
    
    # 核心指标
    m = bt_result["metrics"]
    lines.append(f"### 🏆 核心指标")
    lines.append(f"| 指标 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 交易次数 | {m['total_trades']} |")
    lines.append(f"| 胜率 | **{m['win_rate']}%** |")
    lines.append(f"| 平均收益 | **{m['avg_return']}%** |")
    lines.append(f"| 总收益(复利) | **{m['total_return_compound']}%** |")
    lines.append(f"| 累计收益(算术) | {m['total_return']}% |")
    lines.append(f"| 最大单笔盈利 | {m['best_trade']}% |")
    lines.append(f"| 最大单笔亏损 | {m['worst_trade']}% |")
    lines.append(f"| 盈亏比 | {m['profit_factor']} |")
    lines.append(f"| 夏普比率 | {m['sharpe_ratio']} |")
    lines.append(f"| 平均持仓 | {m['avg_hold_days']}天 |")
    lines.append(f"| 最大连胜 | {m['max_consecutive_wins']}次 |")
    lines.append(f"| 最大连败 | {m['max_consecutive_losses']}次 |")
    lines.append(f"| 买入持有基准 | {m['buy_hold_return']}% |")
    lines.append(f"| 超额收益 | {m['excess_return']}% |")
    lines.append(f"")
    
    # 胜率诊断
    lines.append(f"### 💡 诊断")
    sq = bt_result.get("signal_quality", {})
    if sq and "error" not in sq:
        lines.append(f"**信号发出后各周期上涨概率:**")
        lines.append(f"| 周期 | 样本 | 上涨率 | 平均收益 | 中位数 |")
        lines.append(f"|------|------|--------|----------|--------|")
        for fd, q in sorted(sq.items()):
            lines.append(f"| {fd} | {q['samples']}次 | {q['positive_rate']}% | "
                         f"{q['avg_return']}% | {q['median_return']}% |")
    lines.append(f"")
    
    if m["total_trades"] >= 5:
        if m["win_rate"] >= 50:
            lines.append(f"✅ **结论**: 策略胜率{m['win_rate']}%，有效。建议关注平均收益{m['avg_return']}%")
        else:
            lines.append(f"⚠️ **结论**: 胜率仅{m['win_rate']}%，需优化评分阈值或组合使用")
    else:
        lines.append(f"📌 **结论**: 数据量不足（{m['total_trades']}次交易），继续积累")
    
    # 交易明细
    lines.append(f"")
    lines.append(f"### 📋 最近交易记录")
    trades = bt_result.get("trades", [])
    if trades:
        lines.append(f"| 入场 | 出场 | 持有 | 收益率 | 最大涨幅 | 最大回撤 | 信号评分 |")
        lines.append(f"|------|------|------|--------|----------|----------|----------|")
        for t in trades[-10:]:
            icon = "🟢" if t["is_win"] else "🔴"
            lines.append(f"| {t['entry_date']} | {t['exit_date']} | {t['hold_days']}天 | "
                         f"{icon} {t['pnl_pct']}% | {t['max_rise']}% | {t['max_fall']}% | {t['entry_score']} |")
    
    return "\n".join(lines)


def format_comparison_report(comp_result: Dict) -> str:
    """格式化多策略对比报告"""
    if not comp_result.get("success"):
        return f"❌ 对比失败"
    
    lines = []
    lines.append(f"## ⚔️ 多策略回测对比")
    lines.append(f"")
    lines.append(f"**股票**: {comp_result['code']} {comp_result.get('stock_name', '')}")
    lines.append(f"**回测区间**: {comp_result['period']['start']} ~ {comp_result['period']['end']}")
    lines.append(f"")
    lines.append(f"### 🏆 策略排名")
    lines.append(f"| 排名 | 策略 | 交易次数 | 胜率 | 总收益(复利) | 平均收益 | 盈亏比 | 夏普 |")
    lines.append(f"|------|------|----------|------|--------------|----------|--------|------|")
    
    sorted_strats = sorted(
        [
            (sk, sv)
            for sk, sv in comp_result["strategies"].items()
            if sv.get("success")
        ],
        key=lambda x: x[1]["metrics"]["total_return_compound"],
        reverse=True,
    )
    
    for rank, (sk, sv) in enumerate(sorted_strats, 1):
        m = sv["metrics"]
        wr_icon = "🟢" if m["win_rate"] >= 50 else "🔴"
        lines.append(f"| {rank} | {sv['strategy_name']}({sk}) | {m['total_trades']} | "
                     f"{wr_icon} {m['win_rate']}% | **{m['total_return_compound']}%** | "
                     f"{m['avg_return']}% | {m['profit_factor']} | {m['sharpe_ratio']} |")
    
    return "\n".join(lines)


def format_optimize_report(opt_result: Dict) -> str:
    """格式化参数优化报告"""
    if not opt_result.get("success"):
        return f"❌ 优化失败: {opt_result.get('error', '未知')}"
    
    lines = []
    lines.append(f"## 🔧 策略参数优化")
    lines.append(f"")
    lines.append(f"**股票**: {opt_result['code']}")
    lines.append(f"**策略**: {opt_result['strategy_name']}")
    lines.append(f"**优化参数**: {opt_result['optimized_param']}")
    lines.append(f"**优化目标**: {opt_result['optimization_metric']}")
    lines.append(f"")
    lines.append(f"### 参数排名")
    lines.append(f"| 排名 | {opt_result['optimized_param']} | 交易次数 | 胜率 | 总收益(复利) | 平均收益 | 夏普 | 盈亏比 |")
    lines.append(f"|------|{'---'}|----------|------|--------------|----------|------|--------|")
    
    for r in opt_result["results"]:
        wr_icon = "🟢" if r["win_rate"] >= 50 else "🔴"
        lines.append(f"| #{r['rank']} | {r[opt_result['optimized_param']]} | "
                     f"{r['total_trades']} | {wr_icon} {r['win_rate']}% | "
                     f"**{r.get('total_return_compound', r['total_return'])}%** | "
                     f"{r['avg_return']}% | "
                     f"{r['sharpe_ratio']} | {r['profit_factor']} |")
    
    lines.append(f"")
    if opt_result.get("best"):
        b = opt_result["best"]
        lines.append(f"✅ **最佳**: {opt_result['optimized_param']}={b[opt_result['optimized_param']]}, "
                     f"胜率{b['win_rate']}%, 累计{b['total_return']}%")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════
# 8. 辅助
# ═══════════════════════════════════════════════

def _guess_stock_name(code: str) -> str:
    """尝试从实时数据获取股票名"""
    try:
        suffix = f"sh{code}" if code.startswith(("5", "6", "9")) else f"sz{code}"
        import urllib.request
        req = urllib.request.urlopen(f"http://qt.gtimg.cn/q={suffix}", timeout=5)
        raw = req.read().decode("gbk")
        parts = raw.split("~")
        if len(parts) >= 2:
            return parts[1]
    except:
        pass
    return ""


def save_report(report: str, filename: str = None):
    """保存回测报告到桌面"""
    if filename is None:
        filename = f"策略回测报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    path = os.path.join(REPORT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"✅ 报告已保存: {path}")
    return path


# ═══════════════════════════════════════════════
# 命令行入口
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  uv run python strategy_backtest.py <股票代码> [策略名] [选项]")
        print("")
        print("示例:")
        print("  uv run python strategy_backtest.py 000001                # 所有策略")
        print("  uv run python strategy_backtest.py 000001 youzi          # 指定策略")
        print("  uv run python strategy_backtest.py 000001 --optimize     # 参数优化")
        print("  uv run python strategy_backtest.py 000001 youzi --days=360 --forward=10")
        print("  uv run python strategy_backtest.py 000001 --start=2024-01-01 --end=2024-06-01")
        sys.exit(1)
    
    code = sys.argv[1]
    
    # 解析参数
    specific_strategy = None
    optimize_mode = False
    start_date = None
    end_date = None
    forward_days = 5
    days = 720
    
    for arg in sys.argv[2:]:
        if arg == "--optimize":
            optimize_mode = True
        elif arg.startswith("--start="):
            start_date = arg.split("=", 1)[1]
        elif arg.startswith("--end="):
            end_date = arg.split("=", 1)[1]
        elif arg.startswith("--days="):
            days = int(arg.split("=", 1)[1])
        elif arg.startswith("--forward="):
            forward_days = int(arg.split("=", 1)[1])
        elif arg in STRATEGIES:
            specific_strategy = arg
    
    if optimize_mode and specific_strategy:
        print(f"🔧 参数优化: {code} ({specific_strategy})")
        print("=" * 60)
        result = optimize_strategy(code, specific_strategy, days=days, forward_days=forward_days)
        report = format_optimize_report(result)
        print(report)
        save_report(report)
    
    elif specific_strategy:
        print(f"📊 策略回测: {code} ({specific_strategy})")
        print("=" * 60)
        result = backtest_strategy(
            code, specific_strategy,
            start_date=start_date, end_date=end_date,
            forward_days=forward_days, days=days,
        )
        report = format_backtest_report(result)
        print(report)
        save_report(report)
    
    else:
        print(f"⚔️ 多策略对比: {code}")
        print("=" * 60)
        result = backtest_all_strategies(
            code,
            start_date=start_date, end_date=end_date,
            forward_days=forward_days, days=days,
        )
        report = format_comparison_report(result)
        print(report)
        save_report(report)
        
        # 也输出各策略详情
        for sk, sv in result["strategies"].items():
            if sv.get("success"):
                bt = backtest_strategy(
                    code, sk,
                    start_date=start_date, end_date=end_date,
                    forward_days=forward_days, days=days,
                )
                print(f"\n{'='*60}")
                print(format_backtest_report(bt))
