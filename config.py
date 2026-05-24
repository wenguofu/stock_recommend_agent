#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
a-stock-trading 共享配置模块
所有脚本统一从这里读取 API_BASE，不再各自硬编码端口
"""
import os

# ── API 地址 ──
# 优先级：环境变量 > 默认值
API_BASE = os.environ.get("A_STOCK_API", "http://127.0.0.1:35000")

# ── 端口（与 api_server.py 保持一致） ──
API_PORT = int(os.environ.get("API_PORT", 35000))
