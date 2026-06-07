#!/usr/bin/env python3
"""Layer 1: 技术面宽筛"""
import sys
import os
from typing import Tuple, List, Dict

def is_market_safe_for_screening() -> Tuple[bool, dict]:
    """
    检查大盘环境是否适合筛选
    条件: 涨幅>8%股数 >= 50 且 跌停股数 <= 50

    使用tushare获取全市场完整数据
    """
    try:
        from datetime import datetime, timedelta

        today = datetime.now()
        # 如果是周末，使用最近交易日
        if today.weekday() == 5:  # 周六
            trading_date = (today - timedelta(days=1)).strftime('%Y%m%d')
        elif today.weekday() == 6:  # 周日
            trading_date = (today - timedelta(days=2)).strftime('%Y%m%d')
        else:
            trading_date = today.strftime('%Y%m%d')

        strong_count = 0
        limit_down_count = 0

        # 使用tushare获取全市场日行情
        try:
            import tushare as ts
            from utils_crypto import get_tushare_token

            token = get_tushare_token()
            if token:
                ts.set_token(token)
                pro = ts.pro_api()
                df = pro.daily(trade_date=trading_date)

                if df is not None and not df.empty:
                    strong_count = int(len(df[df['pct_chg'] > 8]))
                    limit_down_count = int(len(df[df['pct_chg'] <= -9]))
        except Exception as e:
            print(f"[market_check] tushare error: {e}")

        # fallback到akshare
        if strong_count == 0:
            try:
                import akshare as ak
                strong = ak.stock_zt_pool_strong_em(date=trading_date)
                strong_count = len(strong[strong['涨跌幅'] > 8]) if '涨跌幅' in strong.columns else 0
                limit_down = ak.stock_zt_pool_dtgc_em(date=trading_date)
                limit_down_count = len(limit_down)
            except Exception:
                pass

        is_safe = (strong_count >= 50) and (limit_down_count <= 50)

        return is_safe, {
            'strong_count': strong_count,
            'limit_down_count': limit_down_count,
            'reason': 'safe' if is_safe else 'market_risk',
            'trading_date': trading_date,
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


def screen_layer1(recommendation_type: str = 'short') -> Dict:
    """
    Layer 1: 技术面宽筛

    Args:
        recommendation_type: 'short' (5-20天) 或 'mid' (1-3个月)

    Returns:
        {
            'candidates': [code, ...],
            'market_check': {...},
            'filter_applied': [...],
            'count': int
        }
    """
    # 1. 大盘环境检查
    is_safe, market_details = is_market_safe_for_screening()

    # 如果大盘环境不安全，返回空结果
    if not is_safe:
        return {
            'candidates': [],
            'market_check': market_details,
            'filter_applied': ['market_safety'],
            'count': 0,
            'recommendation_type': recommendation_type,
            'warning': '大盘环境不安全，暂停筛选'
        }

    # 2. 获取热门板块股票
    from .hot_sector_manager import HotSectorManager
    sector_mgr = HotSectorManager()
    hot_codes = set(sector_mgr.get_all_sector_codes())

    # 如果热门板块配置为空，放宽到所有股票
    if not hot_codes:
        hot_codes = None

    # 3. 从数据库筛选候选股
    from models import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # 基础SQL筛选
        if recommendation_type == 'short':
            # 短线条件
            min_volume = 50000000  # 5000万
            min_days = 120
        else:
            # 中线条件
            min_volume = 100000000  # 1亿
            min_days = 250

        if hot_codes:
            # 热门板块模式：只保留板块内股票
            code_list = list(hot_codes)
            placeholders = ','.join([f':c{i}' for i in range(len(code_list))])
            params = {f'c{i}': code_list[i] for i in range(len(code_list))}

            rows = db.execute(text(f'''
                SELECT b.code, b.name,
                       MAX(b.close) as latest_close,
                       AVG(b.volume) as avg_volume,
                       COUNT(*) as day_count
                FROM backtest_data b
                WHERE b.code REGEXP '^[0-9]{{6}}$'
                AND b.code IN ({placeholders})
                GROUP BY b.code, b.name
                HAVING COUNT(*) >= :min_days
                AND AVG(b.volume) >= :min_volume
                ORDER BY AVG(b.volume) DESC
                LIMIT 500
            '''), {'min_days': min_days, 'min_volume': min_volume, **params}).fetchall()
        else:
            # 全市场模式：无板块限制
            rows = db.execute(text('''
                SELECT b.code, b.name,
                       MAX(b.close) as latest_close,
                       AVG(b.volume) as avg_volume,
                       COUNT(*) as day_count
                FROM backtest_data b
                WHERE b.code REGEXP '^[0-9]{6}$'
                GROUP BY b.code, b.name
                HAVING COUNT(*) >= :min_days
                AND AVG(b.volume) >= :min_volume
                ORDER BY AVG(b.volume) DESC
                LIMIT 500
            '''), {'min_days': min_days, 'min_volume': min_volume}).fetchall()

        candidates = []
        for row in rows:
            candidates.append({
                'code': row[0],
                'name': row[1],
                'avg_volume': float(row[3]) if row[3] else 0
            })

        return {
            'candidates': candidates,
            'market_check': market_details,
            'filter_applied': ['market_safety', 'hot_sectors', 'volume', 'min_days'],
            'count': len(candidates),
            'recommendation_type': recommendation_type
        }

    finally:
        db.close()
