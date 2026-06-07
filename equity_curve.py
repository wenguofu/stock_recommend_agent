#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Equity Curve API — Sprint4

回测后产出每日的累计净值时间序列, 供前端 ECharts 渲染。

输入: 回测结果 (trades 列表) 或 每日 signals
输出: [{date, nav, drawdown, position}, ...]
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd
from sqlalchemy import text
from models import SessionLocal, engine

logger = logging.getLogger(__name__)


def ensure_equity_curve_table():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS backtest_equity_curve (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                code VARCHAR(8) NOT NULL,
                strategy VARCHAR(32) NOT NULL,
                run_id VARCHAR(64) NOT NULL,
                date DATE NOT NULL,
                nav DOUBLE NOT NULL,
                benchmark_nav DOUBLE,
                drawdown DOUBLE,
                position_value DOUBLE,
                cash DOUBLE,
                created_at DATETIME NOT NULL,
                UNIQUE KEY uk_eq_run_date (run_id, date),
                INDEX idx_eq_code_strat (code, strategy),
                INDEX idx_eq_date (date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))


def compute_curve_from_trades(
    code: str,
    strategy: str,
    run_id: str,
    trades: List[Dict],
    initial_capital: float = 100000.0,
    start_date: str = None,
    end_date: str = None,
    benchmark_curve: List[Dict] = None,
) -> List[Dict]:
    """
    从 trades 列表构造 equity curve。
    trades: [{date: 'YYYY-MM-DD', direction: 'buy'|'sell', price, quantity, ...}, ...]
    """
    if not trades:
        return []
    df = pd.DataFrame(trades)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # 计算每日持仓与现金
    df["amount"] = df["price"] * df["quantity"]
    df["signed_amount"] = df.apply(
        lambda r: -r["amount"] if r["direction"] == "buy" else r["amount"], axis=1
    )
    daily = df.groupby("date").agg(
        cash_flow=("signed_amount", "sum"),
        volume=("amount", "sum"),
    ).reset_index()

    # 重采样到每日
    if start_date and end_date:
        idx = pd.date_range(start=start_date, end=end_date, freq="D")
    else:
        idx = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    daily = daily.set_index("date").reindex(idx).fillna(0)
    daily["cash"] = initial_capital + daily["cash_flow"].cumsum()
    # 简化: 不维护持仓估值, 用 cash 当作总资产(单标的 backtest)
    daily["nav"] = daily["cash"]
    daily["drawdown"] = (daily["nav"] / daily["nav"].cummax() - 1) * 100
    daily = daily.reset_index().rename(columns={"index": "date"})
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")

    # 写入表
    save_equity_curve(code, strategy, run_id, daily)

    # 构造返回
    return [
        {
            "date": row["date"],
            "nav": float(row["nav"]),
            "drawdown": float(row["drawdown"]) if pd.notna(row["drawdown"]) else 0.0,
            "cash": float(row["cash"]),
        }
        for _, row in daily.iterrows()
    ]


def save_equity_curve(code: str, strategy: str, run_id: str, daily_df: pd.DataFrame):
    """批量写入 equity curve 表"""
    if daily_df.empty:
        return 0
    db = SessionLocal()
    try:
        rows = []
        for _, r in daily_df.iterrows():
            rows.append({
                "code": code, "strategy": strategy, "run_id": run_id,
                "date": r["date"] if isinstance(r["date"], str) else r["date"].strftime("%Y-%m-%d"),
                "nav": float(r.get("nav", 0)),
                "drawdown": float(r.get("drawdown", 0)) if pd.notna(r.get("drawdown", 0)) else 0,
                "position_value": 0,
                "cash": float(r.get("cash", 0)),
            })
        db.execute(text("""
            INSERT INTO backtest_equity_curve
                (code, strategy, run_id, date, nav, drawdown, position_value, cash, created_at)
            VALUES (:code, :strategy, :run_id, :date, :nav, :drawdown, :position_value, :cash, NOW())
            ON DUPLICATE KEY UPDATE
                nav=VALUES(nav), drawdown=VALUES(drawdown),
                position_value=VALUES(position_value), cash=VALUES(cash)
        """), rows)
        db.commit()
        return len(rows)
    except Exception as e:
        logger.warning(f"save_equity_curve failed: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def get_curve(run_id: str = None, code: str = None, strategy: str = None, days: int = 365) -> List[Dict]:
    """取历史 curve"""
    db = SessionLocal()
    try:
        clauses = ["date >= DATE_SUB(CURDATE(), INTERVAL :d DAY)"]
        params = {"d": days}
        if run_id:
            clauses.append("run_id = :rid")
            params["rid"] = run_id
        if code:
            clauses.append("code = :code")
            params["code"] = code
        if strategy:
            clauses.append("strategy = :strategy")
            params["strategy"] = strategy
        where = " AND ".join(clauses)
        rows = db.execute(text(f"""
            SELECT date, nav, drawdown, cash, position_value
            FROM backtest_equity_curve
            WHERE {where}
            ORDER BY date
        """), params).fetchall()
        return [
            {
                "date": r.date.isoformat() if r.date else None,
                "nav": float(r.nav or 0),
                "drawdown": float(r.drawdown or 0),
                "cash": float(r.cash or 0),
                "position_value": float(r.position_value or 0),
            }
            for r in rows
        ]
    finally:
        db.close()


def register_equity_curve_routes(app):
    """注册 /api/backtest/equity_curve/* 路由"""
    from flask import jsonify, request

    @app.route("/api/backtest/equity_curve", methods=["GET"])
    def equity_curve_get():
        run_id = request.args.get("run_id")
        code = request.args.get("code")
        strategy = request.args.get("strategy")
        days = int(request.args.get("days", 365))
        if not (run_id or (code and strategy)):
            return jsonify({"success": False, "error": "run_id 或 (code+strategy) 必填"}), 400
        curve = get_curve(run_id=run_id, code=code, strategy=strategy, days=days)
        return jsonify({
            "success": True,
            "curve": curve,
            "n": len(curve),
            "max_nav": max((c["nav"] for c in curve), default=0),
            "max_drawdown": min((c["drawdown"] for c in curve), default=0),
        })

    @app.route("/api/backtest/equity_curve", methods=["POST"])
    def equity_curve_post():
        """body: {code, strategy, run_id, trades: [...], initial_capital, start_date, end_date}"""
        data = request.get_json(silent=True) or {}
        for k in ["code", "strategy", "run_id", "trades"]:
            if k not in data:
                return jsonify({"success": False, "error": f"missing {k}"}), 400
        curve = compute_curve_from_trades(
            code=data["code"], strategy=data["strategy"], run_id=data["run_id"],
            trades=data["trades"], initial_capital=data.get("initial_capital", 100000.0),
            start_date=data.get("start_date"), end_date=data.get("end_date"),
        )
        return jsonify({"success": True, "curve": curve, "n": len(curve)})


if __name__ == "__main__":
    ensure_equity_curve_table()
    print("Equity curve table OK")
    # 自检: 写一笔假数据
    sample = [
        {"date": "2024-01-01", "direction": "buy", "price": 100, "quantity": 1000},
        {"date": "2024-02-01", "direction": "sell", "price": 110, "quantity": 1000},
    ]
    curve = compute_curve_from_trades("000001", "test_strategy", "test_run_1", sample,
                                       initial_capital=100000)
    print(f"Generated {len(curve)} days")
    print(f"Final NAV: {curve[-1]['nav']}")
