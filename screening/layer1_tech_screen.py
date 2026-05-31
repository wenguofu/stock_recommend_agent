#!/usr/bin/env python3
"""Layer 1: 技术面宽筛"""
import sys
import os
from typing import Tuple, List, Dict

def is_market_safe_for_screening() -> Tuple[bool, dict]:
    """
    检查大盘环境是否适合筛选
    条件: 涨幅>8%股数 >= 50 且 跌幅>8%股数 <= 50
    """
    try:
        import akshare as ak
        from datetime import datetime

        today = datetime.now().strftime('%Y%m%d')

        # 涨幅>8%股票池
        strong = ak.stock_zt_pool_strong_em(date=today)
        strong_count = len(strong[strong['涨跌幅'] > 8]) if '涨跌幅' in strong.columns else len(strong)

        # 跌停股票池
        dt = ak.stock_zt_pool_dtgc_em(date=today)
        limit_down_count = len(dt)

        is_safe = (strong_count >= 50) and (limit_down_count <= 50)

        return is_safe, {
            'strong_count': strong_count,
            'limit_down_count': limit_down_count,
            'reason': 'safe' if is_safe else 'market_risk',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        # 网络失败时返回安全状态，避免完全阻断
        return True, {
            'strong_count': -1,
            'limit_down_count': -1,
            'reason': 'unknown (api_error)',
            'error': str(e)
        }