#!/usr/bin/env python3
"""自选股快速数据刷新 — 使用腾讯API拉取最新日K"""
import sys, os, urllib.request, sqlite3, json, re, time

sys.path.insert(0, os.path.dirname(__file__))
DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database.db')

def refresh_watchlist():
    conn = sqlite3.connect(DB)
    codes = [r[0] for r in conn.execute("SELECT code FROM watchlist WHERE code NOT LIKE 'SE'").fetchall()]
    conn.close()
    
    ok = 0
    for code in codes:
        try:
            # Use Tencent real-time for today's data
            prefix = 'sh' if code.startswith('6') else 'sz'
            url = f'http://qt.gtimg.cn/q={prefix}{code}'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode('gbk', errors='replace')
            parts = data.split('~')
            
            if len(parts) > 38 and parts[3] != '0.00':
                price = float(parts[3])
                yclose = float(parts[4])
                open_p = float(parts[5])
                high = float(parts[33])
                low = float(parts[34])
                vol = int(parts[6]) * 100
                amount = float(parts[37]) * 10000
                turnover = float(parts[38]) if parts[38] else 0
                date_str = parts[30][:8] if len(parts) > 30 and len(parts[30]) >= 8 else time.strftime('%Y%m%d')
                date_fmt = f'{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}'
                
                conn = sqlite3.connect(DB)
                exists = conn.execute('SELECT 1 FROM backtest_data WHERE code=? AND date=?', (code, date_fmt)).fetchone()
                if not exists:
                    conn.execute('''INSERT OR REPLACE INTO backtest_data (code, date, open, high, low, close, volume, amount, turnover)
                        VALUES (?,?,?,?,?,?,?,?,?)''',
                        (code, date_fmt, open_p, high, low, price, vol, amount, turnover))
                    conn.commit()
                    print(f'  {code}: {date_fmt} O={open_p} H={high} L={low} C={price}')
                    ok += 1
                conn.close()
            time.sleep(0.1)
        except Exception as e:
            print(f'  {code}: ERROR - {e}')
    
    print(f'Done: {ok} inserted')
    return ok

if __name__ == '__main__':
    refresh_watchlist()
