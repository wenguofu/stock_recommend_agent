#!/usr/bin/env python3
"""补拉剩余股票今天(2026-05-19)的K线数据 — 单线程Sina，防限流"""
import json, urllib.request, time, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from db import SessionLocal
from models import BacktestData
from sqlalchemy import func

BUY = 55.51

def sina_kline(code, count=10):
    """Sina API获取日K线"""
    prefix = f"sh{code}" if code.startswith(("5","6","9")) else f"sz{code}"
    url = (f"http://money.finance.sina.com.cn/quotes_service/api/"
           f"json_v2.php/CN_MarketData.getKLineData?"
           f"symbol={prefix}&scale=240&ma=no&datalen={count}")
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Referer': 'http://finance.sina.com.cn',
    })
    data = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
    if data and isinstance(data, list):
        return data
    return []

db = SessionLocal()

# 今天需要补拉的股票（在总池但没今天数据）
today = '2026-05-19'
all_codes = [r[0] for r in db.query(func.distinct(BacktestData.code)).all()]
today_codes = set(r[0] for r in db.query(BacktestData.code).filter(BacktestData.date==today).distinct().all())
missing = [c for c in all_codes if c not in today_codes]
total = len(missing)
print(f"需补拉: {total} 只 (单线程Sina)")

ok = 0
fail = 0
for i, code in enumerate(missing):
    try:
        data = sina_kline(code, count=30)
        if data and len(data) > 0:
            # 找到今天的数据
            today_row = None
            for d in data:
                if d.get("day","")[:10] == today:
                    today_row = d
                    break
            if today_row:
                # 找前一天的close算涨跌幅
                prev_close = 0
                for d in data:
                    if d.get("day","")[:10] < today:
                        prev_close = float(d.get("close", 0))
                
                close = float(today_row.get("close", 0))
                change_pct = 0
                if prev_close > 0:
                    change_pct = (close - prev_close) / prev_close * 100
                
                # 写入数据库
                record = BacktestData(
                    code=code,
                    date=today,
                    open=float(today_row.get("open", 0)),
                    close=close,
                    high=float(today_row.get("high", 0)),
                    low=float(today_row.get("low", 0)),
                    volume=float(today_row.get("volume", 0)),
                    amount=float(today_row.get("amount", 0)) if today_row.get("amount") else 0,
                    change_pct=round(change_pct, 2),
                    turnover=0,  # Sina没有换手率
                    source="sina",
                )
                db.add(record)
                ok += 1
            else:
                fail += 1
        else:
            fail += 1
    except Exception as e:
        fail += 1
    
    if (i+1) % 100 == 0:
        db.commit()
        print(f"  进度 {i+1}/{total} | OK={ok} FAIL={fail}")
    
    time.sleep(0.3)  # 限速

db.commit()
print(f"\n完成! OK={ok} FAIL={fail} (总{total})")

# 查电连技术
dl = db.query(BacktestData).filter(BacktestData.code=='300679', BacktestData.date==today).first()
if dl:
    close = dl.close
    pnl = (close - BUY) / BUY * 100
    print(f"\n电连技术今天: close={close} PnL={pnl:+.2f}% turnover={dl.turnover}")
else:
    print(f"\n电连技术今天暂无数据")
    
    # 单独补拉
    print("单独补拉电连技术...")
    data = sina_kline('300679', count=30)
    for d in data:
        if d.get("day","")[:10] == today:
            prev_close = 0
            for d2 in data:
                if d2.get("day","")[:10] < today:
                    prev_close = float(d2.get("close", 0))
            close = float(d.get("close", 0))
            change_pct = 0
            if prev_close > 0:
                change_pct = (close - prev_close) / prev_close * 100
            record = BacktestData(
                code='300679', date=today,
                open=float(d.get("open",0)), close=close,
                high=float(d.get("high",0)), low=float(d.get("low",0)),
                volume=float(d.get("volume",0)), amount=float(d.get("amount",0)) if d.get("amount") else 0,
                change_pct=round(change_pct,2), turnover=0, source="sina",
            )
            db.add(record)
            db.commit()
            pnl = (close - BUY) / BUY * 100
            print(f"电连技术已补: close={close} PnL={pnl:+.2f}%")
            break

db.close()
