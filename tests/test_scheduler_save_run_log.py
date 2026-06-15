"""测试 _save_run_log 和 _run_task 的日志落库行为"""
import os
import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def test_session(mysql_test_schema, monkeypatch):
    """Rebind models.SessionLocal to test schema — same pattern as test_db.py:22-36"""
    import models
    TestSession = sessionmaker(bind=mysql_test_schema)
    monkeypatch.setattr(models, "SessionLocal", TestSession)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def real_scheduler(mysql_test_schema, monkeypatch):
    """TaskScheduler instance with SessionLocal rebound to test schema"""
    from scheduler import TaskScheduler
    import models
    TestSession = sessionmaker(bind=mysql_test_schema)
    monkeypatch.setattr(models, "SessionLocal", TestSession)
    sched = TaskScheduler()
    yield sched


def test_save_run_log_inserts_row(real_scheduler, test_session):
    from models import SchedulerRunLog

    task = {"name": "板块更新", "type": "cron", "cron": "0 9 * * 1-5"}
    # Use a past timestamp so finished_at - started_at is non-negative
    started = datetime.now()

    real_scheduler._save_run_log(
        task=task,
        started_at=started,
        status="success",
        output="已加载 12 个板块",
        error=None,
        trigger_source="auto",
    )

    rows = test_session.query(SchedulerRunLog).all()
    assert len(rows) == 1
    r = rows[0]
    assert r.task_name == "板块更新"
    assert r.task_type == "cron"
    assert r.schedule == "0 9 * * 1-5"
    assert r.status == "success"
    assert r.output == "已加载 12 个板块"
    assert r.trigger_source == "auto"
    assert r.duration_ms is not None
    assert r.duration_ms >= 0


def test_run_task_writes_running_then_success(real_scheduler, test_session):
    """_run_task 应该在开始时插入 running 行, 完成后 update 为 success"""
    from models import SchedulerRunLog

    task = {
        "name": "板块更新",
        "type": "cron",
        "cron": "0 9 * * 1-5",
        "func": MagicMock(return_value="已加载 12 个板块"),
        "last_output": None,
        "last_error": None,
        "last_run": 0,
        "run_count": 0,
    }

    real_scheduler._run_task(task, trigger_source="auto")

    rows = test_session.query(SchedulerRunLog).filter(
        SchedulerRunLog.task_name == "板块更新"
    ).all()
    # 至少 1 行 (running 插入后 update 为 success, 因此最终 status='success')
    assert len(rows) >= 1
    # 最终行的 status 应该是 success
    assert rows[-1].status == "success"
    assert rows[-1].output == "已加载 12 个板块"
    assert rows[-1].trigger_source == "auto"


def test_run_task_writes_failed_status_on_exception(real_scheduler, test_session):
    """_run_task 在异常时应该写 status=failed + error 文本"""
    from models import SchedulerRunLog

    def boom():
        raise RuntimeError("kaboom")

    task = {
        "name": "板块更新",
        "type": "cron",
        "cron": "0 9 * * 1-5",
        "func": boom,
        "last_output": None,
        "last_error": None,
        "last_run": 0,
        "run_count": 0,
    }

    real_scheduler._run_task(task, trigger_source="manual")

    rows = test_session.query(SchedulerRunLog).filter(
        SchedulerRunLog.task_name == "板块更新"
    ).all()
    assert len(rows) >= 1
    assert rows[-1].status == "failed"
    assert "kaboom" in rows[-1].error
    assert rows[-1].trigger_source == "manual"


def test_run_task_in_flight_no_new_row(real_scheduler, test_session):
    """in-flight 锁命中时不应写新行 (任务没真正执行)"""
    from models import SchedulerRunLog

    task = {
        "name": "板块更新",
        "type": "cron",
        "cron": "0 9 * * 1-5",
        "func": MagicMock(return_value="ok"),
        "last_output": None,
        "last_error": None,
        "last_run": 0,
        "run_count": 0,
        "_in_flight": True,  # 模拟正在执行
    }

    result = real_scheduler._run_task(task, trigger_source="auto")
    assert result is False

    rows = test_session.query(SchedulerRunLog).filter(
        SchedulerRunLog.task_name == "板块更新"
    ).all()
    assert len(rows) == 0  # 没真正执行 → 没写日志
