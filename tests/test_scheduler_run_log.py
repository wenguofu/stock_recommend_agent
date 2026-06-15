"""测试 SchedulerRunLog 模型"""
import os
import sys
import pytest
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def test_session(mysql_test_schema, monkeypatch):
    """Rebind models.SessionLocal to the test schema engine.

    Mirrors the pattern in tests/test_db.py:22-36 to avoid hitting prod DB.
    """
    import models
    TestSession = sessionmaker(bind=mysql_test_schema)
    monkeypatch.setattr(models, "SessionLocal", TestSession)
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def test_insert_and_query_scheduler_run_log(test_session):
    from datetime import datetime
    from models import SchedulerRunLog

    row = SchedulerRunLog(
        task_name="板块更新",
        task_type="cron",
        schedule="0 9 * * 1-5",
        status="success",
        output="已加载 12 个板块",
        error=None,
        started_at=datetime(2026, 6, 16, 9, 0, 12),
        finished_at=datetime(2026, 6, 16, 9, 0, 13),
        duration_ms=1147,
        trigger_source="auto",
    )
    test_session.add(row)
    test_session.commit()
    test_session.refresh(row)

    assert row.id is not None
    assert row.task_name == "板块更新"
    assert row.duration_ms == 1147
    assert row.trigger_source == "auto"


def test_query_scheduler_run_log_by_date(test_session):
    from datetime import datetime, timedelta
    from models import SchedulerRunLog

    # Fixed datetime to avoid midnight-boundary flakiness
    today = datetime(2026, 6, 16, 12, 0, 0)
    yesterday = today - timedelta(days=1)

    test_session.add_all([
        SchedulerRunLog(task_name="板块更新", status="success", started_at=today),
        SchedulerRunLog(task_name="板块更新", status="failed", started_at=yesterday),
    ])
    test_session.commit()

    target = today.strftime("%Y-%m-%d")
    rows = test_session.query(SchedulerRunLog).filter(
        SchedulerRunLog.started_at >= f"{target} 00:00:00",
        SchedulerRunLog.started_at < f"{target} 23:59:59",
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "success"


def test_query_scheduler_run_log_by_task(test_session):
    from datetime import datetime
    from models import SchedulerRunLog

    test_session.add_all([
        SchedulerRunLog(task_name="盯盘提醒", status="success", started_at=datetime.now()),
        SchedulerRunLog(task_name="板块更新", status="success", started_at=datetime.now()),
    ])
    test_session.commit()

    rows = test_session.query(SchedulerRunLog).filter(
        SchedulerRunLog.task_name == "盯盘提醒"
    ).all()
    assert len(rows) == 1
    assert rows[0].task_name == "盯盘提醒"
