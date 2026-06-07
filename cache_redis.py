#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprint5: 轻量级分布式缓存层 (Redis 优先, 内存降级)

用法:
    from cache_redis import get_cache
    cache = get_cache()
    cache.set("key", value, ttl=60)
    v = cache.get("key")

设计:
  - 优先用 redis (REDIS_URL 环境变量)
  - redis 不可用时降级到本地内存 LRU (容量 1024)
  - key 序列化/反序列化用 JSON (datetime/ndarray 兼容)
  - 写入失败不抛异常, 只记日志
"""
import os
import json
import time
import math
import logging
import threading
from collections import OrderedDict
from typing import Any, Optional, Dict, List

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "").strip()
DEFAULT_TTL = int(os.environ.get("CACHE_DEFAULT_TTL", "60"))
MAX_INMEM = int(os.environ.get("CACHE_MAX_INMEM", "1024"))


def _json_default(o):
    import numpy as np
    import pandas as pd
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, pd.DataFrame):
        return o.to_dict(orient="records")
    if isinstance(o, pd.Series):
        return o.to_dict()
    if hasattr(o, "isoformat"):
        return o.isoformat()
    return str(o)


def _json_loads(s: str) -> Any:
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return s


class _InMemoryCache:
    """简单的 LRU + TTL 内存缓存"""
    def __init__(self, max_size: int = MAX_INMEM):
        self._data: "OrderedDict[str, tuple]" = OrderedDict()
        self._lock = threading.Lock()
        self._max = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._data:
                self.misses += 1
                return None
            v, exp = self._data[key]
            if exp and exp < time.time():
                del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return v

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (value, time.time() + ttl if ttl > 0 else 0)
            while len(self._data) > self._max:
                self._data.popitem(last=False)
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._data.pop(key, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> Dict:
        with self._lock:
            return {
                "backend": "memory",
                "size": len(self._data),
                "max_size": self._max,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(self.hits / max(1, self.hits + self.misses), 4),
            }


class _RedisCache:
    """Redis 后端"""
    def __init__(self, url: str):
        import redis
        self._r = redis.from_url(url, socket_timeout=3, decode_responses=False)
        self._prefix = "stock:"

    def _k(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._r.get(self._k(key))
            if raw is None:
                return None
            return _json_loads(raw.decode("utf-8"))
        except Exception as e:
            logger.warning(f"redis get err: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        try:
            payload = json.dumps(value, default=_json_default, ensure_ascii=False).encode("utf-8")
            self._r.setex(self._k(key), max(ttl, 1), payload)
            return True
        except Exception as e:
            logger.warning(f"redis set err: {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            return self._r.delete(self._k(key)) > 0
        except Exception as e:
            logger.warning(f"redis del err: {e}")
            return False

    def clear(self) -> None:
        try:
            for k in self._r.scan_iter(match=f"{self._prefix}*"):
                self._r.delete(k)
        except Exception as e:
            logger.warning(f"redis clear err: {e}")

    def stats(self) -> Dict:
        try:
            info = self._r.info("stats")
            return {
                "backend": "redis",
                "url": REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL,
                "hits": int(info.get("keyspace_hits", 0)),
                "misses": int(info.get("keyspace_misses", 0)),
            }
        except Exception:
            return {"backend": "redis", "error": "stats_unavailable"}


class CacheWrapper:
    """
    统一接口: 自动选 backend
    提供装饰器 cache_result(ttl=60, key_fn=...)
    """
    def __init__(self):
        self._backend = None
        self._init_backend()

    def _init_backend(self):
        if REDIS_URL:
            try:
                self._backend = _RedisCache(REDIS_URL)
                self._backend._r.ping()  # 测试连接
                logger.info(f"cache backend=redis url={REDIS_URL[:30]}")
                return
            except Exception as e:
                logger.warning(f"redis unavailable ({e}), fallback to memory")
        self._backend = _InMemoryCache()
        logger.info("cache backend=memory")

    def get(self, key: str) -> Optional[Any]:
        return self._backend.get(key)

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> bool:
        return self._backend.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        return self._backend.delete(key)

    def clear(self) -> None:
        self._backend.clear()

    def stats(self) -> Dict:
        return self._backend.stats()

    def cached(self, ttl: int = DEFAULT_TTL, key_fn=None):
        """装饰器: 自动 cache 函数结果"""
        def deco(fn):
            def wrap(*args, **kwargs):
                if key_fn:
                    k = key_fn(*args, **kwargs)
                else:
                    k = f"{fn.__module__}.{fn.__name__}:{args}:{sorted(kwargs.items())}"
                v = self.get(k)
                if v is not None:
                    return v
                v = fn(*args, **kwargs)
                self.set(k, v, ttl)
                return v
            return wrap
        return deco


_singleton: Optional[CacheWrapper] = None


def get_cache() -> CacheWrapper:
    global _singleton
    if _singleton is None:
        _singleton = CacheWrapper()
    return _singleton


def register_cache_routes(app):
    """注册缓存管理 API"""
    from flask import jsonify, request

    @app.route("/api/cache/stats", methods=["GET"])
    def cache_stats():
        c = get_cache()
        return jsonify({"success": True, **c.stats()})

    @app.route("/api/cache/clear", methods=["POST"])
    def cache_clear():
        c = get_cache()
        c.clear()
        return jsonify({"success": True, "cleared": True})

    @app.route("/api/cache/get", methods=["GET"])
    def cache_get():
        key = request.args.get("key", "")
        if not key:
            return jsonify({"success": False, "error": "key required"}), 400
        v = get_cache().get(key)
        return jsonify({"success": True, "key": key, "value": v, "hit": v is not None})


if __name__ == "__main__":
    c = get_cache()
    c.set("k1", {"a": 1, "b": [1, 2, 3]}, ttl=10)
    print("get:", c.get("k1"))
    print("stats:", c.stats())
