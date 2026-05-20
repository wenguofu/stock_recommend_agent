#!/usr/bin/env python3
"""
盯盘预警检查脚本 - 每5分钟运行
监控自选股：涨跌阈值、成交量异动、价格突破
no_agent=True 模式：仅当有预警时输出内容（推送到微信）
静默模式：一切正常时不输出任何内容
"""
import json
import os
import sys
from datetime import datetime
from urllib.request import urlopen, Request

API_BASE = os.environ.get('A_STOCK_API', 'http://127.0.0.1:35000')

# 是否交易日检查（跳过周末）
now = datetime.now()
if now.weekday() >= 5:  # 周六=5, 周日=6
    sys.exit(0)  # 静默退出，不推送

# 交易时段：上午9:30-11:30, 下午13:00-15:00
hour = now.hour
minute = now.minute
is_trading = (
    (hour == 9 and minute >= 30) or hour == 10 or (hour == 11 and minute <= 30) or
    hour == 13 or hour == 14 or
    (hour == 15 and minute == 0)
)
if not is_trading:
    sys.exit(0)

# 预警阈值配置
PRICE_CHANGE_WARN = 3.0      # 涨跌幅超过3%预警
VOLUME_SPIKE_RATIO = 2.0     # 成交量超过昨日同时间200%预警
PRICE_HIGH_ALERT = True      # 接近前高预警
VWAP_DEVIATION = 2.0         # 偏离VWAP超过2%预警

def api_get(path):
    """调用后端API"""
    try:
        req = Request(f"{API_BASE}{path}", headers={'User-Agent': 'alert-check/1.0'})
        with urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return None

def format_price(v):
    """格式化价格"""
    if v is None: return '--'
    return f"¥{v:.2f}"

def format_pct(v):
    """格式化百分比"""
    if v is None: return '--'
    sign = '+' if v > 0 else ''
    return f"{sign}{v:.2f}%"

def check_watchlist_alerts():
    """检查自选股预警"""
    # 获取自选股列表
    watch_data = api_get('/api/watchlist')
    if not watch_data or not watch_data.get('success'):
        return None
    
    stocks = watch_data.get('data', [])
    if not stocks:
        return None
    
    alerts = []
    now = datetime.now().strftime('%H:%M')
    is_trading_hours = (
        (datetime.now().hour == 9 and datetime.now().minute >= 30) or
        datetime.now().hour == 10 or
        (datetime.now().hour == 11 and datetime.now().minute <= 30) or
        datetime.now().hour == 13 or
        datetime.now().hour == 14 or
        (datetime.now().hour == 15 and datetime.now().minute == 0)
    )
    
    for stock in stocks:
        code = stock['code']
        name = stock.get('name', code)
        
        # 获取实时行情
        rt = api_get(f'/api/sina/realtime/{code}')
        if not rt:
            continue
        
        current_price = rt.get('current_price')
        # 过滤无效价格（开市前新浪返回0.0）
        if current_price is None or current_price <= 0:
            continue
        change_pct = rt.get('change_percent')
        volume = rt.get('volume')
        high = rt.get('high')
        low = rt.get('low')
        open_price = rt.get('open')
        yest_close = rt.get('yesterday_close')
        
        if current_price is None:
            continue
        
        stock_info = f"{name}({code})"
        
        # 1. 涨跌幅预警
        if change_pct is not None and abs(change_pct) >= PRICE_CHANGE_WARN:
            emoji = '🚀' if change_pct > 0 else '💀'
            alerts.append(f"{emoji} {stock_info} 当前{format_price(current_price)} {format_pct(change_pct)}")
        
        # 2. 放量预警（交易时段才检测）
        if is_trading_hours and volume and volume > 0:
            # 使用5分钟K线判断放量
            kline = api_get(f'/api/sina/minute/{code}?scale=5&datalen=48')
            if kline:
                data = kline.get('data', [])
                if len(data) >= 2:
                    recent_vol = sum(d.get('volume', 0) or 0 for d in data[-2:])
                    prev_vol = sum(d.get('volume', 0) or 0 for d in data[-6:-2]) if len(data) >= 6 else 1
                    if prev_vol > 0 and recent_vol > prev_vol * VOLUME_SPIKE_RATIO:
                        ratio = recent_vol / prev_vol if prev_vol > 0 else 0
                        alerts.append(f"🔥 {stock_info} 放量{ratio:.1f}倍 价格{format_price(current_price)}")
        
        # 3. 持仓盈亏提醒（有持仓时）
        cost = stock.get('cost_price')
        shares = stock.get('shares')
        if cost and shares and shares > 0:
            pnl_pct = (current_price - cost) / cost * 100
            if abs(pnl_pct) >= PRICE_CHANGE_WARN:
                pnl = (current_price - cost) * shares
                emoji = '💰' if pnl > 0 else '📉'
                alerts.append(f"{emoji} {stock_info} 持仓盈亏{format_pct(pnl_pct)} ({'赚' if pnl > 0 else '亏'}{abs(pnl):.0f}元)")
        
        # 4. 接近前高/前低
        if yest_close and high:
            daily_range_pct = (high - low) / yest_close * 100 if low else 0
            if daily_range_pct > 5 and is_trading_hours:
                alerts.append(f"📊 {stock_info} 日内振幅{daily_range_pct:.1f}% 高{format_price(high)} 低{format_price(low)}")
    
    return alerts if alerts else None


def check_sector_news():
    """检查板块热点（减少频率，每30分钟检查一次）"""
    # 只在整半点检查
    now = datetime.now()
    if now.minute not in [0, 30]:
        return None
    
    sectors = api_get('/api/sectors')
    if not sectors or not sectors.get('success'):
        return None
    
    data = sectors.get('data', [])
    hot_sectors = [s for s in data if isinstance(s, dict) and s.get('hot', 0) > 80]
    
    if hot_sectors:
        lines = ["🔥 热门板块"]
        for s in hot_sectors[:3]:
            lines.append(f"  {s.get('name', '')} 热度{s.get('hot', 0)}")
        return lines
    return None


def main():
    alerts = check_watchlist_alerts()
    
    if alerts:
        lines = [
            f"⏰ 盯盘预警 ({datetime.now().strftime('%H:%M')})",
            "─" * 20,
            *alerts,
        ]
        print("\n".join(lines))
    else:
        # 静默输出：no_agent模式下空输出=不推送
        pass


if __name__ == '__main__':
    main()
