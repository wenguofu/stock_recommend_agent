#!/usr/bin/env python3
"""大盘趋势预警推送 — no_agent cron模式 (OpenSpec: market-trend-monitor)"""
import json, os, sys
from datetime import datetime
from urllib.request import urlopen, Request

API = os.environ.get('A_STOCK_API', 'http://127.0.0.1:35000')

now = datetime.now()
if now.weekday() >= 5:
    sys.exit(0)
h, m = now.hour, now.minute
if not ((h==9 and m>=30) or h==10 or (h==11 and m<=30) or h==13 or h==14 or (h==15 and m==0)):
    sys.exit(0)

try:
    req = Request(f'{API}/api/market/monitor/quick', headers={'User-Agent': 'market-alert/1.0'})
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
except Exception:
    sys.exit(0)

level = data.get('warning_level', 'normal')
if level in ('alert', 'danger'):
    score = data.get('total_score', 0)
    emoji = '🟠' if level == 'alert' else '🔴'
    lines = [
        f"{emoji} 大盘趋势预警 ({now.strftime('%H:%M')})",
        f"等级: {data.get('verdict', level)}  评分: {score}/100",
        f"建议: {data.get('suggest', '')}",
    ]
    signals = data.get('signals', [])
    if signals:
        lines.append("─" * 20)
        for s in signals[:5]:
            lines.append(f"  • {s}")
    print("\n".join(lines))
