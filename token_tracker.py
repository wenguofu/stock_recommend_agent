#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Token 用量追踪 — 修复 Sprint3: ai_service 不记录 token 消耗

设计:
  - 内存聚合: 当日总 token / 总成本估算 / 按 provider 分组
  - 可选持久化: 写入 llm_usage 表(若 models 已声明)
  - 失败不抛: tracker 任何异常不能影响主调用链路
"""
import os
import logging
import threading
from collections import defaultdict
from datetime import datetime, date
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 简易成本估算($/1k tokens), 不含企业折扣
_COST_PER_1K_TOKENS = {
    "openai:gpt-4o": 0.005,
    "openai:gpt-4o-mini": 0.00015,
    "openai:gpt-3.5-turbo": 0.0005,
    "deepseek:deepseek-chat": 0.00027,
    "qwen:qwen-turbo": 0.0003,
    "qwen:qwen-plus": 0.0008,
    "siliconflow:Qwen/Qwen2.5-7B-Instruct": 0.00014,
    "gemini:gemini-pro": 0.00125,
    "gemini:gemini-1.5-flash": 0.000075,
    "grok:grok-4-0709": 0.005,
}

_lock = threading.Lock()
_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
    "calls": 0,
})


def _estimate_cost_usd(provider: str, model: str, total_tokens: int) -> float:
    key = f"{provider}:{model}"
    rate = _COST_PER_1K_TOKENS.get(key)
    if rate is None:
        # 兜底: 0.001 $/1k
        rate = 0.001
    return (total_tokens / 1000.0) * rate


def record_usage(provider: str, model: str, usage: Dict[str, Any]) -> None:
    """
    记录一次 LLM 调用的 token 用量。
    失败仅记录警告, 不影响主调用。
    """
    try:
        prompt = int(usage.get("prompt_tokens", 0))
        completion = int(usage.get("completion_tokens", 0))
        total = int(usage.get("total_tokens", prompt + completion))
        if total <= 0:
            return

        with _lock:
            key = f"{provider}:{model}"
            _stats[key]["prompt_tokens"] += prompt
            _stats[key]["completion_tokens"] += completion
            _stats[key]["total_tokens"] += total
            _stats[key]["calls"] += 1

        # 尝试持久化(若表存在)
        try:
            from models import SessionLocal, LLMUsage
            db = SessionLocal()
            try:
                row = LLMUsage(
                    provider=provider,
                    model=model,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    cost_usd=_estimate_cost_usd(provider, model, total),
                )
                db.add(row)
                db.commit()
            except Exception as persist_err:
                # 表可能尚未创建, 静默忽略
                db.rollback()
            finally:
                db.close()
        except ImportError:
            pass

    except Exception as e:
        logger.warning(f"record_usage failed: {e}", exc_info=False)


def get_today_stats() -> Dict[str, Any]:
    """返回当日累计 token / 成本, 按 provider 分组"""
    with _lock:
        out = {
            "date": date.today().isoformat(),
            "by_provider": dict(_stats),
            "total_tokens": sum(s["total_tokens"] for s in _stats.values()),
            "total_calls": sum(s["calls"] for s in _stats.values()),
        }
    # 估算总成本
    total_cost = 0.0
    for key, s in _stats.items():
        provider, model = key.split(":", 1)
        total_cost += _estimate_cost_usd(provider, model, s["total_tokens"])
    out["estimated_cost_usd"] = round(total_cost, 4)
    return out


def reset_stats() -> None:
    """重置内存统计(测试用)"""
    with _lock:
        _stats.clear()


if __name__ == "__main__":
    # 自检
    record_usage("openai", "gpt-4o-mini", {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
    record_usage("deepseek", "deepseek-chat", {"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280})
    import json
    print(json.dumps(get_today_stats(), indent=2, ensure_ascii=False))
