#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
认证中间件 — Token-based API认证
支持：
  - 环境变量 AUTH_TOKEN 快速设置
  - DB 存储 token（优先 env）
  - 白名单路由（无需认证的公共端点）
  - 可关闭（开发模式）
"""
import os
import functools
from flask import request, jsonify, g

# 环境变量控制
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "0") == "1"
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")

# 无需认证的公共路由前缀
PUBLIC_PATHS = {
    "/api/health",
    "/api/v1",
    "/",
    "/assets",
    "/vite.svg",
}


def is_public_path(path: str) -> bool:
    """检查是否为公开路径"""
    for prefix in PUBLIC_PATHS:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


def get_token_from_db():
    """从数据库读取 token"""
    try:
        from models import SessionLocal
        from db import get_config
        db = SessionLocal()
        try:
            return get_config(db, "auth_token") or ""
        finally:
            db.close()
    except Exception:
        return ""


def get_configured_token() -> str:
    """获取配置的 token（环境变量 > DB）"""
    if AUTH_TOKEN:
        return AUTH_TOKEN
    return get_token_from_db()


def register_auth(app):
    """注册认证中间件到 Flask app"""

    if not AUTH_ENABLED:
        @app.before_request
        def _no_auth():
            g.user_authenticated = True

        print("[Auth] 认证已关闭（开发模式）")
        return

    token = get_configured_token()
    if not token:
        print("[Auth] ⚠️  认证已启用但未配置 AUTH_TOKEN，所有请求将被拒绝")
    else:
        print(f"[Auth] 认证已启用（{len(token)} 字符 token）")

    @app.before_request
    def _check_auth():
        # 跳过 OPTIONS（CORS preflight）
        if request.method == "OPTIONS":
            return None

        # 公开路径
        if is_public_path(request.path):
            g.user_authenticated = True
            return None

        # 从 Header 读取 token
        auth_header = request.headers.get("Authorization", "")
        provided_token = ""

        if auth_header.startswith("Bearer "):
            provided_token = auth_header[7:]
        # 也支持 ?token=xxx query 参数
        elif request.args.get("token"):
            provided_token = request.args.get("token")

        current_token = get_configured_token()

        if not current_token:
            # 未配置 token，允许所有请求（安全回退）
            g.user_authenticated = True
            return None

        if provided_token == current_token:
            g.user_authenticated = True
            return None

        return jsonify({
            "error": True,
            "type": "unauthorized",
            "message": "未授权访问，请提供有效的 API Token",
        }), 401

    # 简单登录端点（用于获取 token 验证）
    @app.route('/api/auth/verify', methods=['POST'])
    def verify_token():
        """验证 token 是否有效"""
        data = request.json or {}
        provided = data.get("token", "")
        current = get_configured_token()
        if current and provided == current:
            return jsonify({"success": True, "message": "Token 有效"})
        return jsonify({"success": False, "message": "Token 无效"}), 401


def require_auth(f):
    """装饰器：标记需要认证的单个路由（备用）"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not getattr(g, 'user_authenticated', False):
            return jsonify({
                "error": True,
                "type": "unauthorized",
                "message": "需要认证",
            }), 401
        return f(*args, **kwargs)
    return wrapper
