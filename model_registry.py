#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Model Registry — Sprint4 模型治理

功能:
  - register(): 训练完一个新 checkpoint 后登记到 model_versions 表
  - get_active(model_id): 拿当前生产版本路径
  - get_shadow(model_id): 拿影子版本路径(A/B)
  - promote(version_id): 升为 active (会自动 demote 同 model_id 的其他 active)
  - set_shadow(version_id): 设为影子
  - list_versions(model_id): 列出所有版本

校验:
  - sha256 校验防止路径被替换
  - num_features 防止特征数不匹配
  - mtime 记录版本创建时间
"""
import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import text
from models import SessionLocal, ModelVersion

logger = logging.getLogger(__name__)


def _sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def register(
    model_id: str,
    version: str,
    file_path: str,
    metrics: Dict[str, Any] = None,
    dataset_hash: str = None,
    num_features: int = None,
    notes: str = None,
) -> int:
    """登记一个新模型版本, 返回 version_id"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)
    sha = _sha256_of(file_path)
    size = os.path.getsize(file_path)
    db = SessionLocal()
    try:
        # 同 version 已存在则更新
        existing = db.query(ModelVersion).filter(
            ModelVersion.model_id == model_id,
            ModelVersion.version == version,
        ).first()
        if existing:
            existing.sha256 = sha
            existing.file_size = size
            existing.num_features = num_features
            existing.metrics_json = json.dumps(metrics or {}, ensure_ascii=False)
            existing.dataset_hash = dataset_hash
            existing.notes = notes
            db.commit()
            logger.info(f"[Registry] Updated {model_id} {version} (id={existing.id})")
            return existing.id
        row = ModelVersion(
            model_id=model_id,
            version=version,
            file_path=file_path,
            sha256=sha,
            file_size=size,
            num_features=num_features,
            metrics_json=json.dumps(metrics or {}, ensure_ascii=False),
            dataset_hash=dataset_hash,
            is_active=False,
            is_shadow=False,
            notes=notes,
        )
        db.add(row)
        db.commit()
        logger.info(f"[Registry] Registered {model_id} {version} (id={row.id}, sha={sha[:8]})")
        return row.id
    finally:
        db.close()


def get_active(model_id: str) -> Optional[Dict[str, Any]]:
    """拿当前 active 版本的 checkpoint 信息 (供 ml_predictor.load 用)"""
    db = SessionLocal()
    try:
        row = db.query(ModelVersion).filter(
            ModelVersion.model_id == model_id,
            ModelVersion.is_active == True,  # noqa: E712
        ).order_by(ModelVersion.promoted_at.desc()).first()
        if not row:
            return None
        return _row_to_dict(row)
    finally:
        db.close()


def get_shadow(model_id: str) -> Optional[Dict[str, Any]]:
    """拿当前 shadow 版本"""
    db = SessionLocal()
    try:
        row = db.query(ModelVersion).filter(
            ModelVersion.model_id == model_id,
            ModelVersion.is_shadow == True,  # noqa: E712
        ).order_by(ModelVersion.created_at.desc()).first()
        if not row:
            return None
        return _row_to_dict(row)
    finally:
        db.close()


def promote(version_id: int) -> bool:
    """把指定 version 升为 active, 自动 demote 同 model_id 的其他 active"""
    db = SessionLocal()
    try:
        target = db.query(ModelVersion).filter(ModelVersion.id == version_id).first()
        if not target:
            return False
        # demote 同 model_id 的其他 active
        db.query(ModelVersion).filter(
            ModelVersion.model_id == target.model_id,
            ModelVersion.is_active == True,  # noqa: E712
            ModelVersion.id != version_id,
        ).update({"is_active": False, "promoted_at": None})
        target.is_active = True
        target.promoted_at = datetime.now()
        db.commit()
        logger.info(f"[Registry] Promoted {target.model_id} {target.version} (id={version_id})")
        return True
    finally:
        db.close()


def set_shadow(version_id: int) -> bool:
    """把指定 version 设为 shadow"""
    db = SessionLocal()
    try:
        target = db.query(ModelVersion).filter(ModelVersion.id == version_id).first()
        if not target:
            return False
        db.query(ModelVersion).filter(
            ModelVersion.model_id == target.model_id,
            ModelVersion.is_shadow == True,  # noqa: E712
            ModelVersion.id != version_id,
        ).update({"is_shadow": False})
        target.is_shadow = True
        db.commit()
        logger.info(f"[Registry] Set shadow {target.model_id} {target.version} (id={version_id})")
        return True
    finally:
        db.close()


def list_versions(model_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """列出所有版本 (可按 model_id 过滤)"""
    db = SessionLocal()
    try:
        q = db.query(ModelVersion)
        if model_id:
            q = q.filter(ModelVersion.model_id == model_id)
        rows = q.order_by(ModelVersion.created_at.desc()).limit(limit).all()
        return [_row_to_dict(r) for r in rows]
    finally:
        db.close()


def _row_to_dict(row: ModelVersion) -> Dict[str, Any]:
    metrics = {}
    try:
        metrics = json.loads(row.metrics_json) if row.metrics_json else {}
    except Exception:
        pass
    return {
        "id": row.id,
        "model_id": row.model_id,
        "version": row.version,
        "file_path": row.file_path,
        "sha256": row.sha256,
        "file_size": row.file_size,
        "num_features": row.num_features,
        "metrics": metrics,
        "dataset_hash": row.dataset_hash,
        "is_active": bool(row.is_active),
        "is_shadow": bool(row.is_shadow),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "promoted_at": row.promoted_at.isoformat() if row.promoted_at else None,
        "notes": row.notes,
    }


# ── FastAPI / Flask 风格 API 路由辅助 ──

def register_model_registry_routes(app):
    """注册 /api/ml/registry/* 路由"""
    from flask import jsonify, request

    @app.route("/api/ml/registry/list", methods=["GET"])
    def ml_registry_list():
        model_id = request.args.get("model_id")
        versions = list_versions(model_id=model_id)
        return jsonify({"success": True, "versions": versions, "count": len(versions)})

    @app.route("/api/ml/registry/active", methods=["GET"])
    def ml_registry_active():
        model_id = request.args.get("model_id", "")
        if not model_id:
            return jsonify({"success": False, "error": "model_id required"}), 400
        active = get_active(model_id)
        return jsonify({"success": True, "active": active})

    @app.route("/api/ml/registry/promote", methods=["POST"])
    def ml_registry_promote():
        data = request.get_json(silent=True) or {}
        version_id = data.get("version_id")
        if not version_id:
            return jsonify({"success": False, "error": "version_id required"}), 400
        ok = promote(int(version_id))
        return jsonify({"success": ok})

    @app.route("/api/ml/registry/set_shadow", methods=["POST"])
    def ml_registry_set_shadow():
        data = request.get_json(silent=True) or {}
        version_id = data.get("version_id")
        if not version_id:
            return jsonify({"success": False, "error": "version_id required"}), 400
        ok = set_shadow(int(version_id))
        return jsonify({"success": ok})

    @app.route("/api/ml/registry/register", methods=["POST"])
    def ml_registry_register():
        """训练完调此端点登记, body: {model_id, version, file_path, metrics?, ...}"""
        data = request.get_json(silent=True) or {}
        required = ["model_id", "version", "file_path"]
        for k in required:
            if k not in data:
                return jsonify({"success": False, "error": f"missing {k}"}), 400
        try:
            vid = register(
                model_id=data["model_id"],
                version=data["version"],
                file_path=data["file_path"],
                metrics=data.get("metrics"),
                dataset_hash=data.get("dataset_hash"),
                num_features=data.get("num_features"),
                notes=data.get("notes"),
            )
            return jsonify({"success": True, "version_id": vid})
        except FileNotFoundError as e:
            return jsonify({"success": False, "error": f"file not found: {e}"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    import sys
    # 自检: 列出当前所有版本
    print("Active short_term:", get_active("short_term"))
    print("All versions:", json.dumps(list_versions(), indent=2, ensure_ascii=False))
