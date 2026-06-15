#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调度器路由模块 — 新增 /api/scheduler/runs 端点
"""
from datetime import datetime
from flask import jsonify, request
from error_handler import json_endpoint


def _serialize_run(row):
    """序列化 SchedulerRunLog 行"""
    return {
        "id": row.id,
        "task_name": row.task_name,
        "task_type": row.task_type,
        "schedule": row.schedule,
        "status": row.status,
        "output": row.output or "",
        "error": row.error or "",
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "duration_ms": row.duration_ms,
        "trigger_source": row.trigger_source,
    }


def register_scheduler_routes(app):
    """注册调度器相关路由"""

    @app.route("/api/scheduler/status", methods=["GET"])
    @json_endpoint("raw")
    def scheduler_status():
        """查看调度器任务状态"""
        from scheduler import get_scheduler_status
        return {"success": True, "tasks": get_scheduler_status()}

    @app.route("/api/scheduler/logs", methods=["GET"])
    @json_endpoint("raw")
    def scheduler_logs():
        """查看最近调度器输出 (兼容旧 API, 从 JSON 文件读)"""
        limit = int(request.args.get("limit", 20))
        from scheduler import get_scheduler_outputs
        return {"success": True, "records": get_scheduler_outputs(limit)}

    @app.route("/api/scheduler/trigger", methods=["POST"])
    def scheduler_trigger():
        """手动触发调度器任务(修复 BUG-05: 感知 in-flight, 返 409)"""
        try:
            from scheduler import get_scheduler
            data = request.get_json(silent=True) or {}
            name = data.get("name", "")
            sched = get_scheduler()
            result = sched.run_task(name)
            status_code = 409 if result.get("in_flight") else 200
            return jsonify(result), status_code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/scheduler/runs", methods=["GET"])
    @json_endpoint("raw")
    def scheduler_runs():
        """按日期 (默认今天) 列出 SchedulerRunLog 记录"""
        from models import SchedulerRunLog, SessionLocal
        date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
        task_filter = request.args.get("task", "")
        limit = int(request.args.get("limit", 200))

        db = SessionLocal()
        try:
            q = db.query(SchedulerRunLog).filter(
                SchedulerRunLog.started_at >= f"{date_str} 00:00:00",
                SchedulerRunLog.started_at < f"{date_str} 23:59:59",
            )
            if task_filter:
                q = q.filter(SchedulerRunLog.task_name == task_filter)
            rows = q.order_by(SchedulerRunLog.started_at.desc()).limit(limit).all()
            return {"success": True, "data": [_serialize_run(r) for r in rows]}
        finally:
            db.close()

    @app.route("/api/scheduler/runs/<int:run_id>", methods=["GET"])
    @json_endpoint("raw")
    def scheduler_run_detail(run_id):
        """获取单条 SchedulerRunLog 详情"""
        from models import SchedulerRunLog, SessionLocal
        db = SessionLocal()
        try:
            row = db.get(SchedulerRunLog, run_id)
            if not row:
                return jsonify({"success": False, "error": "not found"}), 404
            return {"success": True, "data": _serialize_run(row)}
        finally:
            db.close()
