#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calibration runtime — Sprint4 校准落地

训练完模型后, 在 val 集上拟合 TemperatureScaler, 把温度参数随 checkpoint 保存。
预测时从 checkpoint 加载 temperature, 应用到 logits 出口。

checkpoint 文件结构(pickle):
  {
    "model_state": ...,
    "model_class": "ShortTermPredictor",
    "config": {...},
    "temperature": 1.234,  # 校准温度
    "calibration_method": "temperature",  # 或 "isotonic"
    "calibration_meta": {"n_samples": 1000, "ece_before": 0.08, "ece_after": 0.02}
  }
"""
import os
import json
import logging
import pickle
from typing import Optional, Dict, Any

import numpy as np
from sqlalchemy import text
from models import SessionLocal, engine

logger = logging.getLogger(__name__)


def ensure_calibration_table():
    """启动建表"""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_calibration (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                model_id VARCHAR(64) NOT NULL,
                version_id INT,
                method VARCHAR(16) NOT NULL,  -- 'temperature' / 'isotonic'
                temperature DOUBLE,
                n_samples INT,
                ece_before DOUBLE,
                ece_after DOUBLE,
                created_at DATETIME NOT NULL,
                UNIQUE KEY uk_calib_model_ver (model_id, version_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))


def fit_temperature_on_val(
    model_id: str,
    val_logits: np.ndarray,
    val_labels: np.ndarray,
    val_probs: np.ndarray = None,
) -> Dict[str, Any]:
    """
    在 val 集上拟合温度标定。
    val_logits: (N, C) 或 (N,) 二分类
    val_labels: (N,) 整数标签
    """
    from dl_models.calibration import TemperatureScaler, IsotonicCalibrator
    from ml_monitor import ece

    if val_labels is None or len(val_labels) < 10:
        return {"success": False, "error": "insufficient val data"}

    # 处理二分类 (1D logits)
    is_binary = val_logits.ndim == 1 or (val_logits.ndim == 2 and val_logits.shape[1] == 1)
    if is_binary:
        if val_logits.ndim == 2:
            val_logits = val_logits.squeeze(-1)
        # 温度标定: 只对正类概率, 二分类温度等价
        scaler = TemperatureScaler()
        # 把 1D 转 2D 形式 (N, 2)
        logits_2d = np.stack([-val_logits, val_logits], axis=1)
        scaler.fit(logits_2d, val_labels)
        calibrated_2d = scaler.calibrate(logits_2d)
        calibrated_pos = calibrated_2d[:, 1]
        # ECE 对比
        y_true = val_labels.astype(int)
        ece_before = ece(y_true, 1.0 / (1.0 + np.exp(-val_logits)))
        ece_after = ece(y_true, calibrated_pos)
        return {
            "success": True,
            "method": "temperature",
            "temperature": scaler.temperature,
            "n_samples": int(len(val_labels)),
            "ece_before": float(ece_before),
            "ece_after": float(ece_after),
        }
    else:
        scaler = TemperatureScaler()
        scaler.fit(val_logits, val_labels)
        calibrated = scaler.calibrate(val_logits)
        ece_before = ece(val_labels, np.exp(val_logits) / np.exp(val_logits).sum(axis=1, keepdims=True)[:, 1])
        ece_after = ece(val_labels, calibrated[:, 1])
        return {
            "success": True,
            "method": "temperature",
            "temperature": scaler.temperature,
            "n_samples": int(len(val_labels)),
            "ece_before": float(ece_before),
            "ece_after": float(ece_after),
        }


def save_calibration(model_id: str, version_id: int, calib_result: Dict) -> int:
    """把校准参数存表"""
    db = SessionLocal()
    try:
        from datetime import datetime
        db.execute(text("""
            INSERT INTO ml_calibration
                (model_id, version_id, method, temperature, n_samples, ece_before, ece_after, created_at)
            VALUES (:mid, :vid, :method, :t, :n, :eb, :ea, :ts)
            ON DUPLICATE KEY UPDATE
                method=VALUES(method), temperature=VALUES(temperature),
                n_samples=VALUES(n_samples), ece_before=VALUES(ece_before),
                ece_after=VALUES(ece_after), created_at=VALUES(created_at)
        """), {
            "mid": model_id, "vid": version_id,
            "method": calib_result.get("method", "temperature"),
            "t": calib_result.get("temperature", 1.0),
            "n": calib_result.get("n_samples", 0),
            "eb": calib_result.get("ece_before"),
            "ea": calib_result.get("ece_after"),
            "ts": datetime.now(),
        })
        db.commit()
        return 1
    except Exception as e:
        logger.warning(f"save_calibration failed: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def get_temperature(model_id: str, version_id: int = None) -> float:
    """从表读 temperature, 默认 1.0 (无标定)"""
    db = SessionLocal()
    try:
        if version_id is not None:
            row = db.execute(text("""
                SELECT temperature FROM ml_calibration
                WHERE model_id = :mid AND version_id = :vid
                ORDER BY created_at DESC LIMIT 1
            """), {"mid": model_id, "vid": version_id}).fetchone()
        else:
            row = db.execute(text("""
                SELECT temperature FROM ml_calibration
                WHERE model_id = :mid
                ORDER BY created_at DESC LIMIT 1
            """), {"mid": model_id}).fetchone()
        return float(row.temperature) if row and row.temperature else 1.0
    finally:
        db.close()


def apply_temperature(prob: float, temperature: float) -> float:
    """把 0-1 概率反向到 logit, 除以 T, 再 sigmoid 回去"""
    if temperature == 1.0 or prob in (0.0, 1.0):
        return prob
    eps = 1e-9
    p = max(min(prob, 1 - eps), eps)
    logit = np.log(p / (1 - p))
    scaled = logit / temperature
    return float(1.0 / (1.0 + np.exp(-scaled)))


def register_calibration_routes(app):
    """注册 /api/ml/calibration/* 路由"""
    from flask import jsonify, request

    @app.route("/api/ml/calibration/fit", methods=["POST"])
    def calibration_fit():
        data = request.get_json(silent=True) or {}
        for k in ["model_id", "val_logits", "val_labels"]:
            if k not in data:
                return jsonify({"success": False, "error": f"missing {k}"}), 400
        val_logits = np.array(data["val_logits"])
        val_labels = np.array(data["val_labels"])
        result = fit_temperature_on_val(data["model_id"], val_logits, val_labels)
        if result.get("success") and data.get("version_id"):
            save_calibration(data["model_id"], int(data["version_id"]), result)
        return jsonify(result)

    @app.route("/api/ml/calibration/get", methods=["GET"])
    def calibration_get():
        model_id = request.args.get("model_id", "short_term")
        version_id = request.args.get("version_id")
        t = get_temperature(model_id, int(version_id) if version_id else None)
        return jsonify({"success": True, "model_id": model_id, "temperature": t})


if __name__ == "__main__":
    ensure_calibration_table()
    # 自检: 模拟 logit + label, 拟合温度
    rng = np.random.default_rng(42)
    logits = rng.normal(0, 2, 200)
    labels = (logits + rng.normal(0, 1, 200) > 0).astype(int)
    result = fit_temperature_on_val("short_term", logits, labels)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("Calibrated prob test:", apply_temperature(0.7, result["temperature"]))
