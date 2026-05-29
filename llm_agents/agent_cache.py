# llm_agents/agent_cache.py
"""Cache for LLM agent analysis results (1-hour TTL, per stock)."""

import time
import hashlib
from typing import Dict, Optional

_cache: Dict[str, tuple] = {}

def _cache_key(stock_code: str, data_hash: str) -> str:
    return hashlib.md5(f"{stock_code}:{data_hash}".encode()).hexdigest()

def get_cached(stock_code: str, data_hash: str, ttl: int = 3600) -> Optional[Dict]:
    key = _cache_key(stock_code, data_hash)
    if key in _cache:
        result, timestamp = _cache[key]
        if time.time() - timestamp < ttl:
            return result
        del _cache[key]
    return None

def set_cache(stock_code: str, data_hash: str, result: Dict):
    key = _cache_key(stock_code, data_hash)
    _cache[key] = (result, time.time())

def clear_expired():
    now = time.time()
    expired = [k for k, (_, ts) in _cache.items() if now - ts > 3600]
    for k in expired:
        del _cache[k]
