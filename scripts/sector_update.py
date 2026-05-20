#!/usr/bin/env python3
"""板块成分股每日更新 - no_agent模式"""
import urllib.request
import json
from datetime import datetime

# 非交易日（周六日）跳过
now = datetime.now()
if now.weekday() >= 5:
    exit(0)

try:
    req = urllib.request.urlopen(
        "http://127.0.0.1:35000/api/sectors/update",
        timeout=60
    )
    data = json.loads(req.read())
    if data.get("success"):
        print(f"✅ 板块数据更新成功")
    else:
        print(f"⚠️ 板块更新返回失败: {data}")
except Exception as e:
    print(f"❌ 板块更新失败: {e}")
