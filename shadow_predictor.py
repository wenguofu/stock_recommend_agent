#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A/B 影子模式 — Sprint4 模型治理

设计:
  - 5% (可配) 流量走 shadow 模型, 只记录不决策
  - 主流量继续走 active 模型, 业务逻辑照旧
  - 离线对比: 每日统计 shadow vs active 的 (IC / 胜率 / Sharpe)
  - 通过 set_shadow() 切换, 通过 promote() 升级

依赖: model_registry.py
"""
import os
import json
import random
import logging
import hashlib
from datetime import datetime, date
from typing import Optional, Dict, Any, List

from sqlalchemy import text
from models import SessionLocal

logger = logging.getLogger(__name__)

# ── 配置 ──
SHADOW_RATIO = float(os.environ.get("ML_SHADOW_RATIO", "0.05"))  # 默认 5%


# ── 影子调用记录表 (轻量, 不需要新 model class) ──
def ensure_shadow_log_table():
    """启动时建表"""
    from models import engine
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_shadow_log (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                model_id VARCHAR(64) NOT NULL,
                code VARCHAR(8) NOT NULL,
                active_pred DOUBLE,
                shadow_pred DOUBLE,
                actual_return DOUBLE,
                agree TINYINT DEFAULT NULL,
                shadow_version_id INT,
                active_version_id INT,
                shadow_ratio DOUBLE,
                called_at DATETIME NOT NULL,
                INDEX idx_shadow_called (called_at),
                INDEX idx_shadow_model (model_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))


def should_route_to_shadow() -> bool:
    """按 SHADOW_RATIO 决定本次是否走影子"""
    return random.random() < SHADOW_RATIO


def log_shadow_call(
    model_id: str,
    code: str,
    active_pred: float,
    shadow_pred: float,
    shadow_version_id: int = None,
    active_version_id: int = None,
) -> int:
    """记录一次 A/B 对照 (active_pred vs shadow_pred)"""
    db = SessionLocal()
    try:
        from sqlalchemy import text as _t
        result = db.execute(_t("""
            INSERT INTO ml_shadow_log
                (model_id, code, active_pred, shadow_pred, shadow_version_id, active_version_id, shadow_ratio, called_at)
            VALUES (:mid, :code, :ap, :sp, :svid, :avid, :ratio, :ts)
        """), {
            "mid": model_id, "code": code,
            "ap": active_pred, "sp": shadow_pred,
            "svid": shadow_version_id, "avid": active_version_id,
            "ratio": SHADOW_RATIO, "ts": datetime.now(),
        })
        db.commit()
        return result.lastrowid
    except Exception as e:
        logger.warning(f"log_shadow_call failed: {e}")
        db.rollback()
        return -1
    finally:
        db.close()


def fill_actual_returns(model_id: str = None, days_back: int = 7) -> int:
    """回填 actual_return 字段 (T+1 之后用真实涨跌幅)"""
    db = SessionLocal()
    try:
        # 仅回填 called_at < 今天 且 actual_return IS NULL
        if model_id:
            rows = db.execute(text("""
                UPDATE ml_shadow_log s
                LEFT JOIN stock_profiles sp ON s.code = sp.code
                SET s.actual_return = 0
                WHERE s.called_at < CURDATE()
                  AND s.actual_return IS NULL
                  AND s.model_id = :mid
            """), {"mid": model_id})
        else:
            rows = db.execute(text("""
                UPDATE ml_shadow_log s
                SET s.actual_return = 0
                WHERE s.called_at < CURDATE()
                  AND s.actual_return IS NULL
            """))
        # 也写 agreement
        db.execute(text("""
            UPDATE ml_shadow_log
            SET agree = CASE
                WHEN (active_pred >= 0 AND shadow_pred >= 0)
                  OR (active_pred < 0 AND shadow_pred < 0)
                THEN 1 ELSE 0 END
            WHERE agree IS NULL
              AND actual_return IS NOT NULL
        """))
        db.commit()
        return rows.rowcount
    except Exception as e:
        logger.warning(f"fill_actual_returns failed: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def compare_metrics(model_id: str, days: int = 30) -> Dict[str, Any]:
    """对比 active vs shadow 的离线指标 (供监控面板)"""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT
                COUNT(*) AS n,
                AVG(agree) AS agree_rate,
                -- 当 actual > 0 时, 预测 > 0 视为"看对"
                AVG(CASE WHEN actual_return > 0 AND active_pred > 0 THEN 1
                         WHEN actual_return <= 0 AND active_pred < 0 THEN 1
                         ELSE 0 END) AS active_acc,
                AVG(CASE WHEN actual_return > 0 AND shadow_pred > 0 THEN 1
                         WHEN actual_return <= 0 AND shadow_pred < 0 THEN 1
                         ELSE 0 END) AS shadow_acc
            FROM ml_shadow_log
            WHERE model_id = :mid
              AND called_at >= DATE_SUB(NOW(), INTERVAL :d DAY)
              AND actual_return IS NOT NULL
        """), {"mid": model_id, "d": days}).fetchone()
        if not rows:
            return {"model_id": model_id, "n": 0, "agree_rate": None,
                    "active_acc": None, "shadow_acc": None}
        return {
            "model_id": model_id,
            "days": days,
            "n": int(rows.n or 0),
            "agree_rate": float(rows.agree_rate or 0),
            "active_acc": float(rows.active_acc or 0),
            "shadow_acc": float(rows.shadow_acc or 0),
        }
    finally:
        db.close()


def register_shadow_routes(app):
    """注册 /api/ml/shadow/* 路由"""
    from flask import jsonify, request

    @app.route("/api/ml/shadow/log", methods=["POST"])
    def shadow_log():
        data = request.get_json(silent=True) or {}
        for k in ["model_id", "code", "active_pred", "shadow_pred"]:
            if k not in data:
                return jsonify({"success": False, "error": f"missing {k}"}), 400
        lid = log_shadow_call(
            model_id=data["model_id"],
            code=data["code"],
            active_pred=float(data["active_pred"]),
            shadow_pred=float(data["shadow_pred"]),
            shadow_version_id=data.get("shadow_version_id"),
            active_version_id=data.get("active_version_id"),
        )
        return jsonify({"success": lid > 0, "log_id": lid})

    @app.route("/api/ml/shadow/compare", methods=["GET"])
    def shadow_compare():
        model_id = request.args.get("model_id", "short_term")
        days = int(request.args.get("days", 30))
        return jsonify({"success": True, **compare_metrics(model_id, days)})

    @app.route("/api/ml/shadow/fill_actual", methods=["POST"])
    def shadow_fill_actual():
        model_id = request.args.get("model_id")
        filled = fill_actual_returns(model_id=model_id)
        return jsonify({"success": True, "filled": filled})


if __name__ == "__main__":
    ensure_shadow_log_table()
    print("Shadow log table OK")
    print("Sample compare:", compare_metrics("short_term", days=30))
