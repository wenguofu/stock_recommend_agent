#!/usr/bin/env python3
"""每日/每周股票推荐生成脚本 - no_agent模式"""
import sys, os, json, urllib.request

sys.path.insert(0, '/Users/wgfu/work/a-stock-trading')
from stock_screener import generate_recommendations

# 判断今日
from datetime import datetime
today = datetime.now()
is_weekday = today.weekday() < 5
is_monday = today.weekday() == 0
hour = today.hour

# 非交易日不生成推荐
if not is_weekday:
    exit(0)

# 每日推荐：盘后生成（15点后或不在交易时段触发时）
rec_type = "daily"
strategies = ["youzi", "lianghua", "jichang"]

# 周一额外生成周推荐
if is_monday and hour >= 15:
    from stock_screener import generate_recommendations
    weekly = generate_recommendations(strategies, top_n=15)
    # 保存到API
    data = json.dumps({"type": "weekly", "strategies": strategies, "top_n": 15}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:35000/api/recommendations/generate",
        data=data, headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=180)
        result = json.loads(resp.read())
        if result.get("success"):
            print(f"✅ 周推荐生成: {result['count']}条推荐, {result['total_unique']}只个股")
    except Exception as e:
        print(f"❌ 周推荐失败: {e}")

# 每日推荐
data = json.dumps({"type": "daily", "strategies": strategies, "top_n": 10}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:35000/api/recommendations/generate",
    data=data, headers={"Content-Type": "application/json"},
    method="POST"
)
try:
    resp = urllib.request.urlopen(req, timeout=180)
    result = json.loads(resp.read())
    if result.get("success") and result.get("count", 0) > 0:
        print(f"📊 每日推荐生成: {result['count']}条推荐, {result['total_unique']}只个股")
        print(f"策略: {', '.join(result['strategies'])}")
except Exception as e:
    print(f"❌ 每日推荐失败: {e}")
