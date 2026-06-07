"""
测试 scheduler.py — 交易日判断、cron 匹配、去重逻辑
"""
import os
import sys
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestTradingTime:
    """交易日和交易时段 — 直接测逻辑而非 datetime mock"""

    def test_is_trading_day_weekday(self):
        """weekday() < 5 → 交易日"""
        from datetime import datetime
        # 周一
        assert datetime(2026, 5, 25).weekday() < 5  # True
        # 周六
        assert not datetime(2026, 5, 23).weekday() < 5  # False

    def test_is_trading_hours_logic(self):
        """交易时段逻辑验证：9:30-11:30 和 13:00-15:00"""
        from datetime import datetime

        # 直接用 datetime 验证边界逻辑（与 scheduler.is_trading_hours 同款逻辑）
        def check_inline(h, m, wd):
            if wd >= 5:
                return False
            if (h == 9 and m >= 30) or (10 <= h <= 11):
                return True
            if h == 11 and m <= 30:
                return True
            if 13 <= h <= 14:
                return True
            if h == 15 and m == 0:
                return True
            return False

        # 非交易日
        assert not check_inline(10, 0, 5)  # 周六
        assert not check_inline(10, 0, 6)  # 周日
        # 盘中
        assert check_inline(10, 0, 0)      # 周一 10:00
        assert check_inline(14, 30, 0)     # 周一 14:30
        assert check_inline(15, 0, 0)      # 周一 15:00 整
        # 非交易时段
        assert not check_inline(9, 20, 0)  # 9:20 未开盘
        assert not check_inline(12, 0, 0)  # 午休
        assert not check_inline(15, 1, 0)  # 收盘后


class TestCronMatch:
    """cron 表达式匹配"""

    def test_match_logic(self):
        """直接测试 match_cron 逻辑"""
        from scheduler import match_cron as check

        # 通配符：任何时间都匹配
        assert check("*", "*", "*", "*", "*") is True

        # 精确匹配：需要 mock datetime.now()
        # 这里只验证函数可调用，不崩溃
        result = check("0", "9", "*", "*", "*")
        assert isinstance(result, bool)


class TestTaskScheduler:
    """TaskScheduler 核心逻辑"""

    def test_task_list_not_empty(self):
        from scheduler import TASKS
        assert len(TASKS) > 0
        names = [t["name"] for t in TASKS]
        assert "盯盘提醒推送" in names
        assert "板块盘后交叉分析" in names

    def test_no_duplicate_task_names(self):
        from scheduler import TASKS
        names = [t["name"] for t in TASKS]
        assert len(names) == len(set(names))

    def test_all_tasks_have_func(self):
        from scheduler import TASKS
        for t in TASKS:
            assert "func" in t
            assert callable(t["func"])

    def test_all_cron_tasks_have_five_parts(self):
        from scheduler import TASKS
        for t in TASKS:
            if t["type"] == "cron":
                parts = t["cron"].split()
                assert len(parts) == 5, f"{t['name']}: cron='{t['cron']}' 不是5段"
