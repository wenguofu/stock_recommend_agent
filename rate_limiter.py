#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
速率限制器 — 基于内存的简单令牌桶实现
"""
import time
import logging
from collections import defaultdict
from functools import wraps
from flask import jsonify, request

logger = logging.getLogger(__name__)

# 默认限制: 30 req/s 全局, 单端点可覆盖
RATE_LIMITS = {
    'default': (60, 60),       # 60次/60秒
    'debate_start': (5, 60),   # 5次/分钟 (启动辩论有LLM成本)
    'ai_analyze': (10, 60),    # 10次/分钟 (单Agent分析)
}

# 存储: {key: [(timestamp, ...)]}
_requests = defaultdict(list)


def _get_client_key() -> str:
    """基于IP的客户端标识"""
    return request.remote_addr or '127.0.0.1'


def _check_rate(key: str, max_requests: int, window: int) -> bool:
    """检查是否超过速率限制"""
    now = time.time()
    window_start = now - window
    # 清理过期记录
    _requests[key] = [t for t in _requests[key] if t > window_start]
    # 检查
    if len(_requests[key]) >= max_requests:
        return False
    _requests[key].append(now)
    return True


def rate_limit(endpoint_name: str = 'default'):
    """装饰器/手动调用的速率限制"""
    max_requests, window = RATE_LIMITS.get(endpoint_name, RATE_LIMITS['default'])

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            client_ip = _get_client_key()
            key = f"{endpoint_name}:{client_ip}"
            if not _check_rate(key, max_requests, window):
                return jsonify({
                    "success": False,
                    "error": f"请求过于频繁，请{window}秒后重试",
                    "type": "rate_limited",
                }), 429
            return f(*args, **kwargs)
        return wrapper
    return decorator
