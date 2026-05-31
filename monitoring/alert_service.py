#!/usr/bin/env python3
"""预警服务"""
import sys
import os
from typing import Dict, List
from datetime import datetime

class AlertService:
    """预警服务"""

    def __init__(self):
        self.alert_history = []

    def check_alerts(self, positions: List[Dict]) -> List[Dict]:
        """检查并生成预警"""
        alerts = []

        for pos in positions:
            code = pos.get('code', '')
            pnl_pct = pos.get('pnl_pct', 0)
            rsi = pos.get('rsi')

            # 止损预警
            if pnl_pct < -7:
                alerts.append({
                    'code': code,
                    'type': 'stop_loss',
                    'message': f'{code} 亏损{pnl_pct:.1f}%，建议止损',
                    'priority': 'high',
                    'timestamp': datetime.now().isoformat()
                })

            # 目标达成预警
            elif pnl_pct > 15:
                alerts.append({
                    'code': code,
                    'type': 'target_hit',
                    'message': f'{code} 盈利{pnl_pct:.1f}%，建议部分止盈',
                    'priority': 'medium',
                    'timestamp': datetime.now().isoformat()
                })

            # RSI超买预警
            if rsi and rsi > 75:
                alerts.append({
                    'code': code,
                    'type': 'rsi_overbought',
                    'message': f'{code} RSI={rsi:.1f}，超买预警',
                    'priority': 'low',
                    'timestamp': datetime.now().isoformat()
                })

        self.alert_history.extend(alerts)
        return alerts

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """获取最近预警"""
        return self.alert_history[-limit:]