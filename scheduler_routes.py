#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调度器路由模块 — 修复 ARCH-01: 拆 api_routes.py

从 api_routes.py 抽离的 /api/scheduler/* 端点,共 3 个:
  - GET  /api/scheduler/status
  - GET  /api/scheduler/logs
  - POST /api/scheduler/trigger
"""
from flask import jsonify, request
from error_handler import json_endpoint


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
        """查看最近调度器输出"""
        limit = int(request.args.get("limit", 20))
        from scheduler import get_scheduler_outputs
        return {"success": True, "records": get_scheduler_outputs(limit)}

    @app.route("/api/scheduler/trigger", methods=["POST"])
    def scheduler_trigger():
        """手动触发调度器任务(修复 BUG-05: 感知 in-flight, 返 409)

        注: 此端点保留手动 try/except 是因为需要返特殊 409 状态码(in_flight).
        """
        try:
            from scheduler import get_scheduler
            data = request.get_json(silent=True) or {}
            name = data.get("name", "")
            sched = get_scheduler()
            result = sched.run_task(name)
            # in_flight 已被 run_task 检测, 返 409
            status_code = 409 if result.get("in_flight") else 200
            return jsonify(result), status_code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
