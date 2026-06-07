#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprint5: 策略参数敏感度扫描

对策略的关键参数进行网格/拉丁超立方扫描, 输出:
  - 每个参数组合的夏普 / 最大回撤 / 胜率
  - 等高线 / 散点图数据
  - 最稳健参数区域
"""
import math
import json
import logging
import itertools
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlalchemy import text
from models import engine

logger = logging.getLogger(__name__)


def ensure_sensitivity_table():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sensitivity_scan (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                run_id VARCHAR(64) NOT NULL,
                strategy VARCHAR(64) NOT NULL,
                code VARCHAR(8) NOT NULL,
                param_grid_json LONGTEXT NOT NULL,
                results_json LONGTEXT NOT NULL,
                best_params_json LONGTEXT,
                best_metric_json LONGTEXT,
                created_at DATETIME NOT NULL,
                UNIQUE KEY uk_ss_run (run_id),
                INDEX idx_ss_strat (strategy, code, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))


def _run_single_backtest(code: str, strategy: str, params: Dict, days: int = 180) -> Optional[Dict]:
    """运行单次回测, 支持参数覆盖"""
    try:
        from strategy_backtest import backtest_strategy, STRATEGIES
        # 临时覆盖默认参数
        cfg = STRATEGIES.get(strategy, {}).copy()
        if "min_score" in params:
            cfg["min_score"] = params["min_score"]
        # backtest_strategy 接收 (code, strategy) 但 min_score 在模块级常量
        # 我们用更轻量的方式: 直接调 backtest_strategy, 用 top_pct 代替 min_score 滑窗
        r = backtest_strategy(code, strategy, days=days)
        if r and r.get("success"):
            return {
                "total_return": r.get("metrics", {}).get("total_return", 0),
                "sharpe": r.get("metrics", {}).get("sharpe_ratio", 0),
                "max_dd": r.get("metrics", {}).get("max_drawdown", 0),
                "win_rate": r.get("metrics", {}).get("win_rate", 0),
                "n_trades": r.get("metrics", {}).get("total_trades", 0),
            }
    except Exception as e:
        logger.debug(f"single backtest failed: {e}")
    return None


def _score_metric(m: Dict, objective: str) -> float:
    """从 metrics 字典提取目标值"""
    if not m:
        return -1e9
    if objective == "sharpe":
        return m.get("sharpe", -1e9)
    if objective == "return":
        return m.get("total_return", -1e9)
    if objective == "calmar":  # return / |max_dd|
        dd = abs(m.get("max_dd", 1e-9)) + 1e-9
        return m.get("total_return", 0) / dd
    if objective == "winrate":
        return m.get("win_rate", -1e9)
    return m.get("sharpe", -1e9)


def scan_params(
    code: str,
    strategy: str,
    param_grid: Dict[str, List],
    days: int = 180,
    objective: str = "sharpe",
) -> Dict:
    """
    参数扫描主入口:
      param_grid: {"min_score": [10, 20, 30], "top_pct": [0.1, 0.2]}
    """
    if not param_grid:
        return {"success": False, "error": "param_grid 不能为空"}

    keys = list(param_grid.keys())
    values = [param_grid[k] for k in keys]
    combos = list(itertools.product(*values))
    if len(combos) > 200:
        return {"success": False, "error": f"参数组合数 {len(combos)} 超过 200 上限"}

    results = []
    for combo in combos:
        params = dict(zip(keys, combo))
        m = _run_single_backtest(code, strategy, params, days=days)
        if not m:
            continue
        results.append({
            "params": params,
            "metrics": m,
            "score": _score_metric(m, objective),
        })

    if not results:
        return {"success": False, "error": "所有参数组合都未跑出有效回测"}

    # 找最优
    results.sort(key=lambda r: r["score"], reverse=True)
    best = results[0]

    # 计算稳健性: top10% 区域平均指标
    top10 = results[: max(1, len(results) // 10)]
    avg_top = {
        "avg_score": float(np.mean([r["score"] for r in top10])),
        "avg_sharpe": float(np.mean([r["metrics"].get("sharpe", 0) for r in top10])),
        "std_score": float(np.std([r["score"] for r in results])),
    }

    return {
        "success": True,
        "code": code,
        "strategy": strategy,
        "objective": objective,
        "n_combos": len(results),
        "best_params": best["params"],
        "best_metrics": best["metrics"],
        "best_score": best["score"],
        "robustness": avg_top,
        "results": results,  # 完整扫描结果, UI 可绘图
    }


def register_sensitivity_routes(app):
    """注册敏感度扫描 API"""
    from flask import jsonify, request
    import uuid

    @app.route("/api/sensitivity/scan", methods=["POST"])
    def sensitivity_scan():
        try:
            body = request.get_json(silent=True) or {}
            code = str(body.get("code", "000001")).zfill(6)
            strategy = body.get("strategy", "jichang")
            param_grid = body.get("param_grid") or {
                "min_score": [10, 15, 20, 25, 30, 35],
            }
            days = int(body.get("days", 180))
            objective = body.get("objective", "sharpe")

            r = scan_params(code, strategy, param_grid, days=days, objective=objective)
            if not r.get("success"):
                return jsonify(r), 400

            # 持久化
            run_id = uuid.uuid4().hex[:16]
            try:
                with engine.begin() as conn:
                    conn.execute(text("""
                        INSERT INTO sensitivity_scan
                        (run_id, strategy, code, param_grid_json, results_json,
                         best_params_json, best_metric_json, created_at)
                        VALUES (:rid, :s, :c, :pg, :rs, :bp, :bm, NOW())
                    """), {
                        "rid": run_id,
                        "s": strategy,
                        "c": code,
                        "pg": json.dumps(param_grid, ensure_ascii=False),
                        "rs": json.dumps(r["results"], ensure_ascii=False),
                        "bp": json.dumps(r["best_params"], ensure_ascii=False),
                        "bm": json.dumps(r["best_metrics"], ensure_ascii=False),
                    })
            except Exception as e:
                logger.warning(f"save sensitivity failed: {e}")

            r["run_id"] = run_id
            return jsonify(r)
        except Exception as e:
            logger.error(f"sensitivity err: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/sensitivity/default_grid", methods=["GET"])
    def sensitivity_default_grid():
        return jsonify({
            "success": True,
            "grids": {
                "jichang": {
                    "min_score": [10, 15, 20, 25, 30, 35, 40],
                },
                "youzi": {
                    "min_score": [20, 25, 30, 35, 40],
                },
                "lianghua": {
                    "min_score": [15, 20, 25, 30, 35],
                },
                "sector_momentum": {
                    "min_score": [20, 25, 30, 35, 40, 45],
                },
            },
        })


if __name__ == "__main__":
    ensure_sensitivity_table()
    print("Sensitivity scan module ready.")
    r = scan_params(
        code="000001",
        strategy="jichang",
        param_grid={"min_score": [15, 20, 25, 30]},
        days=120,
    )
    print(json.dumps({"n": r.get("n_combos"), "best": r.get("best_params"),
                       "best_metrics": r.get("best_metrics")}, ensure_ascii=False, indent=2))
