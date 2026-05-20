#!/usr/bin/env python3
"""用腾讯行情API批量拉今天数据（含换手率）- 收盘后可用"""
import urllib.request, json, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from db import SessionLocal
from models import BacktestData
from sqlalchemy import func

db = SessionLocal()

today = '2026-05-19'
all_codes = [r[0] for r in db.query(func.distinct(BacktestData.code)).all()]
today_codes = set(r[0] for r in db.query(BacktestData.code).filter(BacktestData.date==today).distinct().all())
# 也要拉那些已有数据但没换手率的（之前Sina拉的turnover=0）
need_update = [c for c in all_codes if c not in today_codes]
print(f"需新补: {len(need_update)} 只")

# 清理临时脚本
BATCH = 50  # 每批50只
total = len(need_update)
ok = 0
fail = 0

for start in range(0, total, BATCH):
    batch = need_update[start:start+BATCH]
    # 构建腾讯批量查询URL
    codes_str = ','.join(
        f"sz{c}" if c.startswith(('0','3')) else f"sh{c}" 
        for c in batch
    )
    url = f"http://qt.gtimg.cn/q={codes_str}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        raw = urllib.request.urlopen(req, timeout=30).read().decode('gbk')
        lines = raw.split(';')
        for line in lines:
            if not line.strip():
                continue
            try:
                parts = line.split('~')
                if len(parts) < 39:
                    continue
                code_full = parts[0].split('_')[-1] if '_' in parts[0] else parts[0].replace('v_','').strip('"')
                name = parts[1]
                code = parts[2]
                price = float(parts[3]) if parts[3] else 0
                yclose = float(parts[4]) if parts[4] else 0
                open_p = float(parts[5]) if parts[5] else 0
                volume = float(parts[6]) if parts[6] else 0  # 手
                high_val = float(parts[33]) if parts[33] else 0
                low_val = float(parts[34]) if parts[34] else 0
                amount = float(parts[37]) if parts[37] else 0  # 万
                turnover = float(parts[38]) if parts[38] else 0
                change_pct = ((price - yclose) / yclose * 100) if yclose > 0 else 0
                
                if price <= 0 or yclose <= 0:
                    fail += 1
                    continue
                
                # 入库
                record = BacktestData(
                    code=code, date=today,
                    open=round(open_p, 2), close=round(price, 2),
                    high=round(high_val, 2), low=round(low_val, 2),
                    volume=volume * 100,  # 手转股
                    amount=amount * 10000,  # 万转元
                    change_pct=round(change_pct, 2),
                    turnover=round(turnover, 2),
                    source='tencent',
                )
                db.add(record)
                ok += 1
            except Exception as e:
                fail += 1
    except Exception as e:
        fail += len(batch)
        print(f"  ❌ 批 {start//BATCH+1} 失败: {e}")
    
    if (start // BATCH + 1) % 5 == 0:
        db.commit()
        print(f"进度 {start+BATCH}/{total} | OK={ok} FAIL={fail}")
    
    time.sleep(0.5)  # 限速防ban

db.commit()
# 更新已删除的记录
db.query(BacktestData).filter(BacktestData.code.in_(need_update), BacktestData.date==today, BacktestData.source=='sina').delete(synchronize_session=False)
db.commit()

total_today = db.query(BacktestData).filter(BacktestData.date==today).count()
has_turnover = db.query(BacktestData).filter(BacktestData.date==today, BacktestData.turnover > 0).count()
print(f"\n完成! OK={ok} FAIL={fail}")
print(f"今天总入库: {total_today} | 有换手率: {has_turnover}")

# 查电连
dl = db.query(BacktestData).filter(BacktestData.code=='300679', BacktestData.date==today).first()
if dl:
    buy = 55.51
    pnl = (dl.close - buy) / buy * 100
    print(f"电连技术: 收{dl.close} 换手率{dl.turnover}% PnL:{pnl:+.2f}%")

db.close()
