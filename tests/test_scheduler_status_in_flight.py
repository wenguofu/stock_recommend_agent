"""测试 get_status 暴露 in_flight + current_started_at"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_get_status_includes_in_flight_false_by_default():
    from scheduler import TaskScheduler
    sched = TaskScheduler()
    status = sched.get_status()
    assert isinstance(status, list)
    assert len(status) > 0
    for row in status:
        assert "in_flight" in row
        assert "current_started_at" in row
        assert row["in_flight"] is False
        assert row["current_started_at"] is None


def test_get_status_in_flight_true_when_set():
    from scheduler import TaskScheduler
    sched = TaskScheduler()
    target = sched.tasks[0]
    target["_in_flight"] = True
    target["_current_started_at"] = datetime(2026, 6, 16, 11, 0, 0).isoformat()

    status = sched.get_status()
    row = next(r for r in status if r["name"] == target["name"])
    assert row["in_flight"] is True
    assert row["current_started_at"] == "2026-06-16T11:00:00"