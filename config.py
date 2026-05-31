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

# ── 数据库 ──
# 默认 SQLite，切换到 MySQL 时设置环境变量:
#   export DATABASE_URL="mysql+pymysql://stock_user:stock_pass_2024@127.0.0.1:3306/stock_trading"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///database.db")
