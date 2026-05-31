#!/usr/bin/env python3
"""每日监控"""
import sys
import os
from typing import Dict, List
from datetime import datetime

class DailyMonitor:
    """每日监控器"""

    def __init__(self):
        self.alerts = []

    def get_daily_status(self) -> Dict:
        """获取每日监控状态"""
        from screening.recommendation_engine import get_recommendations
        from models import SessionLocal
        from sqlalchemy import text

        db = SessionLocal()
        try:
            # 获取持仓
            positions = db.execute(text('''
                SELECT code, name, shares, avg_cost, current_price
                FROM paper_positions
                WHERE shares > 0
            ''')).fetchall()

            # 获取当前推荐
            recommendations = get_recommendations(recommendation_type='short', top_n=5)

            # 检查持仓股票状态
            position_alerts = []
            for pos in positions:
                code = pos[0]
                shares = pos[2]
                cost = pos[3]
                current_price = pos[4] or 0

                pnl_pct = (current_price / cost - 1) * 100 if cost and cost > 0 else 0

                alert = None
                if pnl_pct < -7:
                    alert = {'code': code, 'type': 'stop_loss', 'pnl_pct': round(pnl_pct, 2)}
                elif pnl_pct > 15:
                    alert = {'code': code, 'type': 'target_hit', 'pnl_pct': round(pnl_pct, 2)}

                if alert:
                    position_alerts.append(alert)

            return {
                'positions': [
                    {
                        'code': p[0],
                        'name': p[1],
                        'shares': p[2],
                        'cost': p[3],
                        'current_price': p[4],
                        'pnl_pct': round((p[4]/p[3]-1)*100, 2) if p[3] and p[3] > 0 and p[4] else 0
                    } for p in positions
                ],
                'recommendations': recommendations.get('recommendations', []),
                'position_alerts': position_alerts,
                'generated_at': datetime.now().isoformat()
            }
        finally:
            db.close()