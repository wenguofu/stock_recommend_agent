#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""美股数据获取模块 - 使用Yahoo Finance API"""

import requests
import pandas as pd
import json
import time
from datetime import datetime, timedelta


def get_us_daily_kline(code, count=240):
    """获取美股日K线数据（从yfinance）"""
    try:
        import yfinance as yf
        ticker = yf.Ticker(code.upper())
        df = ticker.history(period="1y")
        
        if df is None or len(df) == 0:
            print(f"[yfinance] {code} 无数据")
            return None
        
        df = df.reset_index()
        result_df = pd.DataFrame({
            'date': df['Date'].dt.strftime('%Y-%m-%d'),
            'open': df['Open'],
            'high': df['High'],
            'low': df['Low'],
            'close': df['Close'],
            'volume': df['Volume'],
        })
        
        if len(result_df) > count:
            result_df = result_df.tail(count)
        
        print(f"[yfinance] {code} 获取到 {len(result_df)} 条日K数据")
        return result_df
        
    except Exception as e:
        print(f"[yfinance] {code} 获取日K失败: {e}")
        return None


def get_us_realtime_from_yahoo(code):
    """从Yahoo Finance获取美股实时行情（备选）"""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{code.upper()}?range=1d&interval=1d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        
        data = response.json()
        meta = data.get('chart', {}).get('result', [{}])[0].get('meta', {})
        
        return {
            'code': code.upper(),
            'name': meta.get('shortName', code.upper()),
            'current_price': meta.get('regularMarketPrice'),
            'previous_close': meta.get('chartPreviousClose'),
            'high': meta.get('regularMarketDayHigh'),
            'low': meta.get('regularMarketDayLow'),
            'change_percent': meta.get('regularMarketChangePercent'),
        }
    except Exception as e:
        print(f"[Yahoo] {code} 实时行情失败: {e}")
        return None
