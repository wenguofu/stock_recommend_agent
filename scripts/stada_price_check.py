#!/usr/bin/env python3
"""斯达半导(603290)价格监控 - no_agent模式，零token消耗"""
import urllib.request
import sys
from datetime import datetime

# 非交易时段跳过
now = datetime.now()
hour = now.hour
minute = now.minute
day = now.weekday()  # 0=Mon, 6=Sun
if day >= 5:  # 周末
    sys.exit(0)
if hour < 9 or hour > 15:  # 非交易时间（宽泛判断，后续精确）
    sys.exit(0)
if hour == 9 and minute < 30:
    sys.exit(0)
if hour == 11 and minute > 30:
    sys.exit(0)
if hour == 15 and minute > 0:
    sys.exit(0)
if hour == 12:
    sys.exit(0)

# 获取实时数据
try:
    req = urllib.request.urlopen("http://qt.gtimg.cn/q=sh603290", timeout=8)
    raw = req.read().decode("gbk")
    parts = raw.split("~")
    if len(parts) < 4:
        sys.exit(0)
    current = float(parts[3])  # 第4个字段是当前价
except:
    sys.exit(0)

if current <= 110:
    print(f"🚨 斯达半导(603290)价格已到达买入区！")
    print(f"当前价: {current:.2f} 元")
    print(f"推荐买入区: ≤110元")
    print(f"建议立即登录模拟盘建仓买入")
elif current <= 119:
    print(f"📊 斯达半导(603290)价格接近买入区")
    print(f"当前价: {current:.2f} 元")
    print(f"推荐买入区: ≤110元，还需再跌一点")
    print("做好准备")
else:
    sys.exit(0)  # 高于119静默
