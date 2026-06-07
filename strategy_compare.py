#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略对比可视化 — Sprint4

输入: 多个策略的 equity curve (4 条)
输出: 叠加曲线 + 滚动 Sharpe + 关键指标对比表

API: /api/strategy/compare?strategies=ma_cross,momentum,jichang,youzi&code=000001&days=180
"""
import os
import json
import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy import text
from models import SessionLocal, engine

logger = logging.getLogger(__name__)


def ensure_strategy_compare_table():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS strategy_compare_run (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                run_id VARCHAR(64) NOT NULL,
                code VARCHAR(8),
                strategies_json TEXT NOT NULL,  -- ['ma_cross', 'momentum', ...]
                results_json LONGTEXT,           -- {strategy: {nav: [...], sharpe, drawdown, ...}}
                best_strategy VARCHAR(32),
                created_at DATETIME NOT NULL,
                UNIQUE KEY uk_sc_run (run_id),
                INDEX idx_sc_code (code),
                INDEX idx_sc_date (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))


def compute_rolling_sharpe(navs: pd.Series, window: int = 20, risk_free: float = 0.0) -> pd.Series:
    """滚动 Sharpe (年化)"""
    rets = navs.pct_change()
    roll_mean = rets.rolling(window).mean()
    roll_std = rets.rolling(window).std()
    sharpe = (roll_mean - risk_free) / (roll_std + 1e-9) * np.sqrt(252)
    return sharpe.fillna(0)


def compute_max_drawdown(navs: pd.Series) -> float:
    """最大回撤 (%)"""
    cummax = navs.cummax()
    dd = (navs - cummax) / cummax
    return float(dd.min() * 100)


def compute_total_return(navs: pd.Series) -> float:
    """总收益 (%)"""
    if len(navs) < 2 or navs.iloc[0] == 0:
        return 0.0
    return float((navs.iloc[-1] / navs.iloc[0] - 1) * 100)


def compute_sharpe(navs: pd.Series, risk_free: float = 0.0) -> float:
    """整体 Sharpe"""
    rets = navs.pct_change().dropna()
    if len(rets) < 2:
        return 0.0
    excess = rets - risk_free / 252
    return float(excess.mean() / (excess.std() + 1e-9) * np.sqrt(252))


def compare_strategies(
    code: str,
    strategies: List[str],
    days: int = 180,
) -> Dict:
    """
    对比多个策略在同一只股票上的回测表现。
    每个策略回测得到 nav 序列, 合并后输出比较表。
    """
    results = {}
    for strat in strategies:
        try:
            from strategy_backtest import backtest_strategy
            r = backtest_strategy(code, strat, days=days, initial_capital=100000.0)
            if r and r.get("success") and r.get("trades"):
                nav_curve = r.get("nav_curve") or _synthesize_nav(r["trades"], 100000.0)
                results[strat] = {
                    "nav": nav_curve,
                    "metrics": {
                        "total_return": r.get("total_return", 0),
                        "sharpe": r.get("sharpe_ratio", 0),
                        "max_drawdown": r.get("max_drawdown", 0),
                        "win_rate": r.get("win_rate", 0),
                        "trade_count": len(r.get("trades", [])),
                    }
                }
            else:
                results[strat] = {
                    "nav": [],
                    "metrics": {"error": r.get("error", "no trades") if r else "no result"},
                }
        except Exception as e:
            logger.warning(f"backtest {strat} on {code} failed: {e}")
            results[strat] = {"nav": [], "metrics": {"error": str(e)}}

    # 找最优策略(夏普最高)
    best = None
    best_sharpe = -1e9
    for strat, data in results.items():
        m = data.get("metrics", {})
        s = m.get("sharpe", -1e9) if isinstance(m.get("sharpe"), (int, float)) else -1e9
        if s > best_sharpe:
            best_sharpe = s
            best = strat

    return {
        "code": code,
        "strategies": strategies,
        "results": results,
        "best_strategy": best,
        "days": days,
    }


def _synthesize_nav(trades: list, initial: float) -> List[Dict]:
    """从 trades 简单构造 nav 序列"""
    if not trades:
        return []
    cash = initial
    pos = 0
    rows = []
    for t in trades:
        price = t.get("price", 0)
        qty = t.get("quantity", 0)
        d = t.get("date")
        if t.get("direction") == "buy":
            cash -= price * qty
            pos += qty
        else:
            cash += price * qty
            pos -= qty
        nav = cash + pos * price
        rows.append({"date": d, "nav": float(nav)})
    return rows


def register_strategy_compare_routes(app):
    """注册 /api/strategy/compare 路由"""
    from flask import jsonify, request

    @app.route("/api/strategy/compare", methods=["GET"])
    def strategy_compare():
        code = request.args.get("code", "000001")
        strategies = request.args.get("strategies", "ma_cross,momentum,jichang,youzi").split(",")
        strategies = [s.strip() for s in strategies if s.strip()]
        days = int(request.args.get("days", 180))
        result = compare_strategies(code, strategies, days)
        return jsonify({"success": True, **result})


if __name__ == "__main__":
    ensure_strategy_compare_table()
    print("Strategy compare table OK")
    r = compare_strategies("000001", ["ma_cross", "momentum"], days=60)
    print(json.dumps({k: v.get("metrics") for k, v in r["results"].items()}, indent=2, ensure_ascii=False))
    print("Best:", r["best_strategy"])
