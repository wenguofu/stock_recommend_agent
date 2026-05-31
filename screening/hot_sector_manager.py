#!/usr/bin/env python3
"""热门板块动态管理器 - 每周更新热门板块列表"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

HOT_SECTORS_FILE = os.path.join(os.path.dirname(__file__), 'hot_sectors.json')

# 默认热门板块
DEFAULT_SECTORS = [
    {"name": "芯片/半导体", "codes": [], "score": 80},
    {"name": "新能源汽车", "codes": [], "score": 75},
    {"name": "医药生物", "codes": [], "score": 70},
    {"name": "人工智能", "codes": [], "score": 70},
    {"name": "光伏/储能", "codes": [], "score": 65},
    {"name": "军工", "codes": [], "score": 60},
]

class HotSectorManager:
    """热门板块管理器"""

    def __init__(self, config_file: str = HOT_SECTORS_FILE):
        self.config_file = config_file
        self._load_config()

    def _load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {
                'version': '1.0.0',
                'updated_at': datetime.now().strftime('%Y-%m-%d'),
                'sectors': DEFAULT_SECTORS.copy()
            }
            self._save_config()

    def _save_config(self):
        """保存配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def get_current_sectors(self) -> List[str]:
        """获取当前热门板块名称列表"""
        return [s['name'] for s in self.config.get('sectors', [])]

    def get_sector_codes(self, sector_name: str) -> List[str]:
        """获取指定板块的成分股"""
        for sector in self.config.get('sectors', []):
            if sector['name'] == sector_name:
                return sector.get('codes', [])
        return []

    def get_all_sector_codes(self) -> List[str]:
        """获取所有热门板块的成分股（去重）"""
        codes = set()
        for sector in self.config.get('sectors', []):
            codes.update(sector.get('codes', []))
        return list(codes)

    def update_weekly(self) -> Dict:
        """
        每周检查更新热门板块
        基于近20日涨幅、成交额等指标更新
        """
        try:
            import akshare as ak
            import numpy as np

            # 获取行业板块数据
            df = ak.stock_board_industry_name_em()

            scored_sectors = []
            for _, row in df.iterrows():
                name = row.get('名称', '')
                if not name:
                    continue
                # 涨幅、成交额等评分
                change_pct = row.get('涨跌幅', 0) or 0
                amount = row.get('成交额', 0) or 0

                # 简单评分：涨幅*0.6 + 成交额标准化*0.4
                amount_norm = min(amount / 1e10, 1.0) if amount else 0
                score = change_pct * 0.6 + amount_norm * 0.4 * 100

                scored_sectors.append({
                    'name': name,
                    'codes': [],  # 板块成分股待补充
                    'score': round(score, 2),
                    'change_pct': round(float(change_pct), 2) if change_pct else 0,
                    'amount': amount
                })

            # 按评分排序，保留Top 8
            scored_sectors.sort(key=lambda x: x['score'], reverse=True)
            top_sectors = scored_sectors[:8]

            self.config['sectors'] = top_sectors
            self.config['updated_at'] = datetime.now().strftime('%Y-%m-%d')
            self._save_config()

            return {
                'success': True,
                'updated_count': len(top_sectors),
                'top_sectors': [s['name'] for s in top_sectors]
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_config(self) -> Dict:
        """获取完整配置"""
        return self.config.copy()