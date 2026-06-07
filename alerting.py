#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sprint5: 多通道告警推送

支持:
  - 飞书机器人 (webhook)
  - 钉钉机器人 (webhook + 加签可选)
  - 通用 Webhook (POST JSON)
  - 控制台 (logger)

配置: 通过环境变量 / 配置文件
  FEISHU_WEBHOOK_URL, DINGTALK_WEBHOOK_URL, DINGTALK_SECRET,
  GENERIC_WEBHOOK_URL

调用: send_alert(level, title, content, tags=None)
"""
import os
import json
import time
import hmac
import hashlib
import base64
import logging
import urllib.request
import urllib.parse
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ── 配置加载 ──
FEISHU_URL = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
DINGTALK_URL = os.environ.get("DINGTALK_WEBHOOK_URL", "").strip()
DINGTALK_SECRET = os.environ.get("DINGTALK_SECRET", "").strip()
GENERIC_WEBHOOK_URL = os.environ.get("GENERIC_WEBHOOK_URL", "").strip()
ALERT_LEVEL_FILTER = os.environ.get("ALERT_LEVEL_FILTER", "info").strip().lower()  # info/warn/error

_LEVELS = {"info": 0, "warn": 1, "error": 2}


def _should_send(level: str) -> bool:
    return _LEVELS.get(level, 0) >= _LEVELS.get(ALERT_LEVEL_FILTER, 0)


def _post_json(url: str, payload: Dict, timeout: int = 5) -> bool:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            logger.info(f"alert POST {url} → {resp.status} {body[:200]}")
            return 200 <= resp.status < 300
    except Exception as e:
        logger.warning(f"alert POST failed {url}: {e}")
        return False


def _dingtalk_sign(secret: str) -> str:
    """钉钉加签 (v1)"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return f"&timestamp={timestamp}&sign={sign}"


def send_feishu(title: str, content: str, at_mobiles: Optional[List[str]] = None) -> bool:
    if not FEISHU_URL:
        return False
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": content},
                }
            ],
        },
    }
    if at_mobiles:
        payload["card"]["elements"].append({
            "tag": "at", "mobiles": at_mobiles,
        })
    return _post_json(FEISHU_URL, payload)


def send_dingtalk(title: str, content: str, at_mobiles: Optional[List[str]] = None) -> bool:
    if not DINGTALK_URL:
        return False
    url = DINGTALK_URL
    if DINGTALK_SECRET:
        url = f"{DINGTALK_URL}?{_dingtalk_sign(DINGTALK_SECRET).lstrip('&')}"
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"# {title}\n\n{content}\n",
        },
        "at": {
            "atMobiles": at_mobiles or [],
            "isAtAll": False,
        },
    }
    return _post_json(url, payload)


def send_generic(title: str, content: str, level: str, tags: Optional[List[str]] = None) -> bool:
    if not GENERIC_WEBHOOK_URL:
        return False
    payload = {
        "title": title,
        "content": content,
        "level": level,
        "tags": tags or [],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": "stock-trading",
    }
    return _post_json(GENERIC_WEBHOOK_URL, payload)


def send_alert(
    level: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    channels: Optional[List[str]] = None,
) -> Dict:
    """
    主入口: 发送一条告警到所有配置的通道
    level: info / warn / error
    channels: None = 全部启用通道, [] = 仅控制台
    """
    if not _should_send(level):
        return {"sent": False, "reason": "below_level_filter"}

    log_fn = {"info": logger.info, "warn": logger.warning, "error": logger.error}.get(level, logger.info)
    log_fn(f"[ALERT {level}] {title}: {content}")

    if channels is None:
        channels = []
        if FEISHU_URL:
            channels.append("feishu")
        if DINGTALK_URL:
            channels.append("dingtalk")
        if GENERIC_WEBHOOK_URL:
            channels.append("generic")
        if not channels:
            channels = ["console"]

    results = {}
    for ch in channels:
        if ch == "feishu":
            results["feishu"] = send_feishu(title, content)
        elif ch == "dingtalk":
            results["dingtalk"] = send_dingtalk(title, content)
        elif ch == "generic":
            results["generic"] = send_generic(title, content, level, tags)
        elif ch == "console":
            results["console"] = True
        else:
            results[ch] = False

    return {"sent": True, "level": level, "channels": results, "title": title}


def register_alert_routes(app):
    """注册 /api/alert/send 路由 + 配置查看"""
    from flask import jsonify, request

    @app.route("/api/alert/send", methods=["POST"])
    def alert_send():
        try:
            body = request.get_json(silent=True) or {}
            level = body.get("level", "info")
            title = body.get("title", "Stock Alert")
            content = body.get("content", "")
            tags = body.get("tags") or []
            channels = body.get("channels")
            if not _should_send(level):
                return jsonify({"success": True, "sent": False, "reason": "filtered"})
            result = send_alert(level, title, content, tags=tags, channels=channels)
            return jsonify({"success": True, **result})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/alert/channels", methods=["GET"])
    def alert_channels():
        return jsonify({
            "success": True,
            "configured": {
                "feishu": bool(FEISHU_URL),
                "dingtalk": bool(DINGTALK_URL),
                "dingtalk_signed": bool(DINGTALK_SECRET),
                "generic": bool(GENERIC_WEBHOOK_URL),
            },
            "level_filter": ALERT_LEVEL_FILTER,
        })


if __name__ == "__main__":
    print(json.dumps(send_alert("info", "测试", "smoke test"), ensure_ascii=False))
