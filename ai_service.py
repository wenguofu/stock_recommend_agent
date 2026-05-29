#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI服务调用模块"""

import requests
import os
import time
from typing import Dict, Optional

# ── Provider配置 ──
# 每个provider只需定义URL和是否需要Bearer token
# 兼容OpenAI接口格式的provider只需配base_url即可

PROVIDER_CONFIG = {
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "bearer": True,
    },
    "deepseek": {
        "url": "https://api.deepseek.com/v1/chat/completions",
        "bearer": True,
    },
    "qwen": {
        "url": os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1") + "/chat/completions",
        "bearer": True,
    },
    "siliconflow": {
        "url": os.getenv("SILICONFLOW_API_BASE", "https://api.siliconflow.cn") + "/v1/chat/completions",
        "bearer": True,
    },
    "grok": {
        "url": "https://api.x.ai/v1/chat/completions",
        "bearer": True,
    },
}

DEFAULT_MODEL_MAP = {
    "openai": "gpt-3.5-turbo",
    "deepseek": "deepseek-chat",
    "qwen": "qwen-turbo",
    "gemini": "gemini-pro",
    "siliconflow": "Qwen/Qwen2.5-7B-Instruct",
    "grok": "grok-4-0709",
}


class AIService:
    """统一的AI服务调用类"""

    # ═══════════════════════════════════════════
    # 通用OpenAI兼容调用
    # ═══════════════════════════════════════════

    @staticmethod
    def _call_openai_compatible(url: str, api_key: str, model: str, prompt: str) -> str:
        """通用OpenAI兼容API调用 (适用于 openai/deepseek/qwen/siliconflow/grok)"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 8192,
        }
        response = requests.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    # ═══════════════════════════════════════════
    # Gemini (非OpenAI兼容格式)
    # ═══════════════════════════════════════════

    @staticmethod
    def _call_gemini(api_key: str, model: str, prompt: str) -> str:
        """调用Gemini API"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(url, json=data, timeout=120)
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    # ═══════════════════════════════════════════
    # 统一调用接口
    # ═══════════════════════════════════════════

    @classmethod
    def call_agent(cls, provider: str, api_key: str, model: str, prompt: str) -> str:
        """统一调用接口，自动重试可恢复的错误"""
        if provider == "gemini":
            call_fn = lambda: cls._call_gemini(api_key, model, prompt)
        elif provider in PROVIDER_CONFIG:
            url = PROVIDER_CONFIG[provider]["url"]
            call_fn = lambda: cls._call_openai_compatible(url, api_key, model, prompt)
        else:
            raise ValueError(f"不支持的AI提供商: {provider}")

        last_error = None
        for attempt in range(3):
            try:
                return call_fn()
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                time.sleep(1 + attempt * 2)
            except Exception as e:
                last_error = e
                break

        raise last_error

    # ═══════════════════════════════════════════
    # 结构化JSON输出
    # ═══════════════════════════════════════════

    @staticmethod
    def call_agent_structured(provider: str, api_key: str, model: str,
                               messages: list, json_schema: dict = None) -> dict:
        """
        Call LLM with structured JSON output.
        messages: list of {"role": "user"|"system", "content": "..."}
        json_schema: optional JSON Schema for response_format (not enforced, for documentation)
        Returns parsed dict.
        """
        import json as _json

        if provider == "gemini":
            return AIService._call_gemini_structured(api_key, model, messages)

        url = PROVIDER_CONFIG[provider]["url"]
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,  # lower temp for structured decisions
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
        }

        response = requests.post(url, headers=headers, json=data, timeout=120)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

        # Parse and validate
        try:
            result = _json.loads(content)
            return result
        except _json.JSONDecodeError:
            # Try extracting JSON from markdown code block
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
                return _json.loads(content)
            raise ValueError(f"Failed to parse JSON from LLM response: {content[:200]}")

    @staticmethod
    def _call_gemini_structured(api_key: str, model: str, messages: list) -> dict:
        """Gemini structured call — add JSON instruction to the last message."""
        import json as _json

        # Append JSON format instruction
        json_instruction = "\n\nRespond with valid JSON only. No markdown, no code blocks, no explanation outside the JSON object."
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += json_instruction

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        gemini_contents = []
        for msg in messages:
            gemini_contents.append({"parts": [{"text": msg["content"]}]})

        data = {"contents": gemini_contents}
        response = requests.post(url, json=data, timeout=120)
        response.raise_for_status()
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"]

        try:
            return _json.loads(content)
        except _json.JSONDecodeError:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
                return _json.loads(content)
            raise ValueError(f"Failed to parse JSON from Gemini response: {content[:200]}")

    # ═══════════════════════════════════════════
    # 模型列表
    # ═══════════════════════════════════════════

    @staticmethod
    def _fetch_models_openai_compatible(base_url: str, api_key: str) -> list:
        """通用获取模型列表 (OpenAI兼容接口)"""
        url = base_url.rstrip("/") + "/v1/models" if "/v1" not in base_url else base_url.rstrip("/") + "/models"
        # 统一使用 /models 端点
        if "/chat/completions" in base_url:
            url = base_url.replace("/chat/completions", "/models")
        try:
            response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
            response.raise_for_status()
            models = [m["id"] for m in response.json().get("data", [])]
            return sorted(models) if models else []
        except Exception:
            return []

    @staticmethod
    def get_models(provider: str, api_key: str) -> list:
        """获取指定提供商的可用模型列表"""
        fallback_map = {
            "openai": ["gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"],
            "deepseek": ["deepseek-chat", "deepseek-coder"],
            "qwen": ["qwen-turbo", "qwen-plus", "qwen-max"],
            "gemini": ["gemini-pro", "gemini-pro-vision"],
            "grok": ["grok-4-0709", "grok-beta", "grok-2"],
        }

        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                models = [m.get("name", "").replace("models/", "")
                          for m in response.json().get("models", []) if m.get("name")]
                return sorted(models) if models else fallback_map["gemini"]
            except Exception:
                return fallback_map["gemini"]

        if provider == "openai":
            models = AIService._fetch_models_openai_compatible("https://api.openai.com", api_key)
            if models:
                models = [m for m in models if "gpt" in m.lower() and ("chat" in m.lower() or "turbo" in m.lower())]
                return sorted(models)
            return fallback_map["openai"]

        if provider in PROVIDER_CONFIG:
            url = PROVIDER_CONFIG[provider]["url"]
            base_url = url.replace("/chat/completions", "").replace("/v1/chat/completions", "")
            models = AIService._fetch_models_openai_compatible(base_url, api_key)
            if models:
                return models

        # 硅基流动的特殊fallback
        if provider == "siliconflow":
            return [
                "Qwen/Qwen2.5-72B-Instruct", "Qwen/Qwen2.5-32B-Instruct",
                "Qwen/Qwen2.5-14B-Instruct", "Qwen/Qwen2.5-7B-Instruct",
                "meta-llama/Llama-3.1-70B-Instruct", "meta-llama/Llama-3.1-8B-Instruct",
                "deepseek-ai/DeepSeek-V2.5", "deepseek-ai/DeepSeek-V2",
            ]

        return fallback_map.get(provider, [])

    # ═══════════════════════════════════════════
    # 连接测试
    # ═══════════════════════════════════════════

    @staticmethod
    def test_connection(provider: str, api_key: str, model: str = None) -> dict:
        """测试API连接"""
        try:
            if not model:
                model = DEFAULT_MODEL_MAP.get(provider, "gpt-3.5-turbo")

            test_prompt = "Hello, please respond with 'OK' to confirm the connection."
            result = AIService.call_agent(provider, api_key, model, test_prompt)

            return {
                "success": True,
                "message": "连接成功",
                "response": result[:100],
            }
        except requests.HTTPError as e:
            response_text = ""
            try:
                response_text = e.response.text if e.response is not None else ""
            except Exception:
                response_text = ""
            detail = str(e)
            if response_text:
                detail = f"{detail} | {response_text[:200]}"
            return {"success": False, "message": f"连接失败: {detail}"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)}"}
