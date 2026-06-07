"""主线预判 /sector-prediction"""
from conftest import BasePageTest


class SectorPredictionTest(BasePageTest):
    path = "/sector-prediction"
    title = "主线预判"
    interactive = [
        {"selector": "button:has-text('分析')", "description": "分析按钮", "optional": True},
        {"selector": "button:has-text('刷新')", "description": "刷新", "optional": True},
    ]
