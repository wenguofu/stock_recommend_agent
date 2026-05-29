#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WebSocket 实时推送模块
提供：
  - 辩论任务进度实时推送（替代前端轮询）
  - 调度器告警通知
  - 价格预警推送
"""
import json
import logging
from datetime import datetime

logger = logging.getLogger("websocket")

# 全局 socketio 实例（由 api_server.py 初始化）
_socketio = None


def get_socketio():
    """获取 socketio 实例（延迟初始化）"""
    global _socketio
    return _socketio


def init_socketio(app):
    """初始化 Flask-SocketIO 并注册事件"""
    global _socketio
    try:
        from flask_socketio import SocketIO
    except ImportError:
        logger.warning("flask-socketio 未安装，WebSocket 功能不可用")
        return None

    _socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    @_socketio.on("connect")
    def handle_connect():
        logger.info(f"WebSocket 客户端连接")

    @_socketio.on("disconnect")
    def handle_disconnect():
        logger.info(f"WebSocket 客户端断开")

    @_socketio.on("subscribe_debate")
    def handle_subscribe_debate(data):
        """客户端订阅指定辩论任务进度"""
        job_id = data.get("job_id", "")
        if job_id:
            from flask_socketio import join_room
            join_room(f"debate_{job_id}")
            logger.info(f"客户端订阅辩论任务: {job_id}")

    @_socketio.on("unsubscribe_debate")
    def handle_unsubscribe_debate(data):
        """取消订阅"""
        job_id = data.get("job_id", "")
        if job_id:
            from flask_socketio import leave_room
            leave_room(f"debate_{job_id}")

    logger.info("WebSocket 服务已启动")
    return _socketio


# ═══════════════════════════════════════════
# 推送辅助函数（供其他模块调用）
# ═══════════════════════════════════════════

def emit_debate_progress(job_id: str, progress: int, status: str,
                         phase: str = "", detail: str = ""):
    """推送辩论任务进度"""
    sio = get_socketio()
    if not sio:
        return
    try:
        sio.emit("debate_progress", {
            "job_id": job_id,
            "progress": progress,
            "status": status,
            "phase": phase,
            "detail": detail,
            "timestamp": datetime.now().isoformat(),
        }, room=f"debate_{job_id}")
    except Exception as e:
        logger.error(f"WebSocket 推送失败: {e}")


def emit_debate_complete(job_id: str, report_md: str = ""):
    """推送辩论任务完成"""
    sio = get_socketio()
    if not sio:
        return
    try:
        sio.emit("debate_complete", {
            "job_id": job_id,
            "report_preview": report_md[:500] if report_md else "",
            "timestamp": datetime.now().isoformat(),
        }, room=f"debate_{job_id}")
    except Exception as e:
        logger.error(f"WebSocket 推送失败: {e}")


def emit_alert(alert_type: str, title: str, message: str, level: str = "info"):
    """推送全局告警（调度器任务输出、价格预警等）"""
    sio = get_socketio()
    if not sio:
        return
    try:
        sio.emit("alert", {
            "type": alert_type,
            "title": title,
            "message": message,
            "level": level,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"WebSocket 告警推送失败: {e}")


def emit_price_update(code: str, price: float, change_pct: float):
    """推送价格更新"""
    sio = get_socketio()
    if not sio:
        return
    try:
        sio.emit("price_update", {
            "code": code,
            "price": price,
            "change_pct": change_pct,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"WebSocket 价格推送失败: {e}")
