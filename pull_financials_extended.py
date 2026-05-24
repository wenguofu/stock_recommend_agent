#!/usr/bin/env python3
"""批量拉取主线股基本面数据到DB（带重试+退避）"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(__file__))

from fundamental_data import fetch_and_cache
from models import SessionLocal

# 从板块缓存加载主线股
with open(os.path.join(os.path.dirname(__file__), 'sector_data_cache.json')) as f:
    sectors = json.load(f)

themes = ['人工智能', '半导体', '机器人', '算力/数据中心', '新能源车', '消费电子']
codes = set()
for theme in themes:
    if theme in sectors:
        for s in sectors[theme].get('stocks', []):
            codes.add(s['code'])

codes = sorted(codes)[:100]
print(f"拉取 {len(codes)} 只主线股财报...")

ok = 0
fail = 0
failed_codes = []
MAX_RETRIES = 3
BASE_DELAY = 0.5

db = SessionLocal()

for i, code in enumerate(codes):
    success = False
    for attempt in range(MAX_RETRIES):
        try:
            result = fetch_and_cache(code, db=db)
            if result and result.get('revenue'):
                ok += 1
                success = True
                break
            else:
                if attempt < MAX_RETRIES - 1:
                    wait = BASE_DELAY * (2 ** attempt) * 2
                    time.sleep(wait)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = BASE_DELAY * (2 ** attempt) * 2
                time.sleep(wait)

    if not success:
        fail += 1
        failed_codes.append(code)

    if (i + 1) % 20 == 0 or i == len(codes) - 1:
        print(f"  [{i+1}/{len(codes)}] ok={ok} fail={fail}")

    time.sleep(BASE_DELAY)

print(f"\n完成: ok={ok} fail={fail}")
if failed_codes:
    print(f"失败股票: {', '.join(failed_codes)}")

db.close()
