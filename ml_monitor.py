#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ML 性能监控 — Sprint4 模型治理

每日任务: 计算 PSI / KS / 滚动 IC / ECE / Brier Score
阈值越界 → 写 alert + 推飞书/钉钉 (由 alert_pusher 接管)

指标定义:
  - PSI (Population Stability Index): 衡量特征分布漂移
    < 0.1: 稳定; 0.1-0.25: 轻微漂移; > 0.25: 严重漂移
  - KS (Kolmogorov-Smirnov): 衡量预测分数对正负样本的区分度
    越大越好, max=1
  - IC (Information Coefficient): Spearman 相关(预测 vs 实际收益)
  - ECE (Expected Calibration Error): 校准误差
  - Brier Score: 均方误差,越小越好
"""
import os
import json
import math
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from models import SessionLocal, engine

logger = logging.getLogger(__name__)


# ── 阈值 (可由业务配置覆盖) ──
PSI_WARN = 0.10
PSI_ALERT = 0.25
KS_WARN = 0.05   # 退化
ECE_WARN = 0.05
BRIER_WARN = 0.30
IC_WARN = 0.01   # 接近 0 = 无预测力


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index"""
    if len(expected) < bins or len(actual) < bins:
        return 0.0
    quantiles = np.quantile(expected, np.linspace(0, 1, bins + 1))
    quantiles[0] = -np.inf
    quantiles[-1] = np.inf
    e_counts = np.histogram(expected, bins=quantiles)[0]
    a_counts = np.histogram(actual, bins=quantiles)[0]
    # 避免 0
    e_pct = (e_counts + 1e-6) / (e_counts.sum() + 1e-6 * bins)
    a_pct = (a_counts + 1e-6) / (a_counts.sum() + 1e-6 * bins)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def ks_statistic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Kolmogorov-Smirnov 二分类区分度"""
    if len(y_true) == 0:
        return 0.0
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.0
    # KS = max |CDF_pos - CDF_neg|
    all_thresholds = np.sort(np.unique(y_score))
    ks_values = []
    for t in all_thresholds:
        fpr = (neg >= t).mean()
        tpr = (pos >= t).mean()
        ks_values.append(abs(tpr - fpr))
    return float(max(ks_values)) if ks_values else 0.0


def ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error"""
    if len(y_true) == 0:
        return 0.0
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece_val = 0.0
    for lo, hi in zip(bin_boundaries[:-1], bin_boundaries[1:]):
        mask = (y_prob >= lo) & (y_prob < hi)
        if mask.sum() == 0:
            continue
        avg_conf = y_prob[mask].mean()
        avg_acc = y_true[mask].mean()
        ece_val += mask.sum() * abs(avg_conf - avg_acc)
    return float(ece_val / len(y_true))


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Brier = mean((p - y)^2)"""
    if len(y_true) == 0:
        return 0.0
    return float(np.mean((y_prob - y_true) ** 2))


def spearman_ic(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Spearman Rank IC"""
    if len(y_true) < 2:
        return 0.0
    df = pd.DataFrame({"y": y_true, "s": y_score}).rank()
    n = len(df)
    d2 = ((df["y"] - df["s"]) ** 2).sum()
    return float(1 - 6 * d2 / (n * (n * n - 1)))


def compute_daily_metrics(model_id: str = "short_term", days_back: int = 30) -> Dict[str, Any]:
    """
    从 ml_shadow_log 取近 N 天数据, 计算监控指标。
    返回 dict 含 psi/ks/ic/ece/brier + 每项的告警级别。
    """
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT code, active_pred, shadow_pred, actual_return, called_at
            FROM ml_shadow_log
            WHERE model_id = :mid
              AND called_at >= DATE_SUB(NOW(), INTERVAL :d DAY)
              AND actual_return IS NOT NULL
            ORDER BY called_at
        """), {"mid": model_id, "d": days_back}).fetchall()
        if not rows or len(rows) < 10:
            return {
                "model_id": model_id, "n": 0, "status": "insufficient_data",
                "metrics": {}, "alerts": [],
            }

        df = pd.DataFrame(rows, columns=["code", "active_pred", "shadow_pred", "actual_return", "called_at"])
        # 转 numpy
        y_score = df["shadow_pred"].fillna(0).to_numpy()
        y_return = df["actual_return"].fillna(0).to_numpy()
        y_true = (y_return > 0).astype(int)  # 上涨=1

        # PSI: 预测分布漂移(对比最近 7 天 vs 前 7 天)
        mid = len(df) // 2
        if mid >= 10:
            psi_val = psi(y_score[:mid], y_score[mid:], bins=10)
        else:
            psi_val = 0.0

        ks_val = ks_statistic(y_true, y_score)
        ece_val = ece(y_true, y_score)
        brier = brier_score(y_true, y_score)
        ic_val = spearman_ic(y_return, y_score)

        # 告警判定
        alerts = []
        if psi_val > PSI_ALERT:
            alerts.append({"level": "alert", "metric": "psi", "value": round(psi_val, 4),
                           "threshold": PSI_ALERT, "msg": f"PSI 严重漂移 {psi_val:.3f} > {PSI_ALERT}"})
        elif psi_val > PSI_WARN:
            alerts.append({"level": "warn", "metric": "psi", "value": round(psi_val, 4),
                           "threshold": PSI_WARN, "msg": f"PSI 轻微漂移 {psi_val:.3f} > {PSI_WARN}"})
        if ic_val is not None and abs(ic_val) < IC_WARN:
            alerts.append({"level": "warn", "metric": "ic", "value": round(ic_val, 4),
                           "threshold": IC_WARN, "msg": f"IC 接近 0 ({ic_val:.4f}), 预测力失效"})
        if ece_val > ECE_WARN:
            alerts.append({"level": "warn", "metric": "ece", "value": round(ece_val, 4),
                           "threshold": ECE_WARN, "msg": f"ECE 校准差 {ece_val:.3f} > {ECE_WARN}"})
        if brier > BRIER_WARN:
            alerts.append({"level": "warn", "metric": "brier", "value": round(brier, 4),
                           "threshold": BRIER_WARN, "msg": f"Brier 偏高 {brier:.3f} > {BRIER_WARN}"})

        return {
            "model_id": model_id,
            "n": int(len(df)),
            "days": days_back,
            "status": "ok",
            "metrics": {
                "psi": round(psi_val, 4),
                "ks": round(ks_val, 4),
                "ic": round(ic_val, 4),
                "ece": round(ece_val, 4),
                "brier": round(brier, 4),
            },
            "alerts": alerts,
            "computed_at": datetime.now().isoformat(),
        }
    finally:
        db.close()


def ensure_ml_metrics_table():
    """启动建表"""
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ml_daily_metrics (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                model_id VARCHAR(64) NOT NULL,
                date DATE NOT NULL,
                n INT,
                psi DOUBLE,
                ks DOUBLE,
                ic DOUBLE,
                ece DOUBLE,
                brier DOUBLE,
                alerts_json TEXT,
                computed_at DATETIME,
                UNIQUE KEY uk_ml_model_date (model_id, date),
                INDEX idx_ml_date (date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))


def save_daily_metrics(metrics: Dict[str, Any]) -> int:
    """把监控结果写入表 (供趋势图)"""
    db = SessionLocal()
    try:
        m = metrics.get("metrics", {})
        db.execute(text("""
            INSERT INTO ml_daily_metrics
                (model_id, date, n, psi, ks, ic, ece, brier, alerts_json, computed_at)
            VALUES (:mid, CURDATE(), :n, :psi, :ks, :ic, :ece, :brier, :alerts, :ts)
            ON DUPLICATE KEY UPDATE
                n=VALUES(n), psi=VALUES(psi), ks=VALUES(ks), ic=VALUES(ic),
                ece=VALUES(ece), brier=VALUES(brier), alerts_json=VALUES(alerts_json),
                computed_at=VALUES(computed_at)
        """), {
            "mid": metrics["model_id"],
            "n": metrics.get("n", 0),
            "psi": m.get("psi"), "ks": m.get("ks"),
            "ic": m.get("ic"), "ece": m.get("ece"), "brier": m.get("brier"),
            "alerts": json.dumps(metrics.get("alerts", []), ensure_ascii=False),
            "ts": datetime.now(),
        })
        db.commit()
        return 1
    except Exception as e:
        logger.warning(f"save_daily_metrics failed: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def get_trend(model_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """取最近 N 天指标趋势"""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT date, n, psi, ks, ic, ece, brier, alerts_json
            FROM ml_daily_metrics
            WHERE model_id = :mid
              AND date >= DATE_SUB(CURDATE(), INTERVAL :d DAY)
            ORDER BY date
        """), {"mid": model_id, "d": days}).fetchall()
        result = []
        for r in rows:
            alerts = []
            try:
                alerts = json.loads(r.alerts_json or "[]")
            except Exception:
                pass
            result.append({
                "date": r.date.isoformat() if r.date else None,
                "n": r.n, "psi": r.psi, "ks": r.ks, "ic": r.ic,
                "ece": r.ece, "brier": r.brier, "alerts": alerts,
            })
        return result
    finally:
        db.close()


def register_ml_monitor_routes(app):
    """注册 /api/ml/monitor/* 路由"""
    from flask import jsonify, request

    @app.route("/api/ml/monitor/daily", methods=["GET"])
    def ml_monitor_daily():
        model_id = request.args.get("model_id", "short_term")
        days = int(request.args.get("days", 30))
        m = compute_daily_metrics(model_id, days)
        save_daily_metrics(m)
        return jsonify({"success": True, **m})

    @app.route("/api/ml/monitor/trend", methods=["GET"])
    def ml_monitor_trend():
        model_id = request.args.get("model_id", "short_term")
        days = int(request.args.get("days", 30))
        trend = get_trend(model_id, days)
        return jsonify({"success": True, "model_id": model_id, "trend": trend, "n": len(trend)})


if __name__ == "__main__":
    ensure_ml_metrics_table()
    for mid in ["short_term", "mid_term", "regime"]:
        m = compute_daily_metrics(mid, 30)
        save_daily_metrics(m)
        print(f"{mid}: {m.get('status')} | alerts={len(m.get('alerts', []))} | n={m.get('n', 0)}")
