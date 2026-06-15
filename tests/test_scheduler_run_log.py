"""测试 SchedulerRunLog 模型"""
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def session(mysql_test_schema):
    from models import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_insert_and_query_scheduler_run_log(mysql_test_schema):
    from datetime import datetime
    from models import SchedulerRunLog, SessionLocal

    db = SessionLocal()
    try:
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
        db.add(row)
        db.commit()
        db.refresh(row)

        assert row.id is not None
        assert row.task_name == "板块更新"
        assert row.duration_ms == 1147
        assert row.trigger_source == "auto"
    finally:
        db.close()


def test_query_scheduler_run_log_by_date(session):
    from datetime import datetime, timedelta
    from models import SchedulerRunLog

    # today
    today_row = SchedulerRunLog(
        task_name="板块更新", status="success", started_at=datetime.now()
    )
    # yesterday
    yesterday_row = SchedulerRunLog(
        task_name="板块更新", status="failed",
        started_at=datetime.now() - timedelta(days=1),
    )
    session.add_all([today_row, yesterday_row])
    session.commit()

    target = datetime.now().strftime("%Y-%m-%d")
    rows = session.query(SchedulerRunLog).filter(
        SchedulerRunLog.started_at >= f"{target} 00:00:00",
        SchedulerRunLog.started_at < f"{target} 23:59:59",
    ).all()
    assert len(rows) == 1
    assert rows[0].status == "success"


def test_query_scheduler_run_log_by_task(session):
    from datetime import datetime
    from models import SchedulerRunLog

    session.add_all([
        SchedulerRunLog(task_name="盯盘提醒", status="success", started_at=datetime.now()),
        SchedulerRunLog(task_name="板块更新", status="success", started_at=datetime.now()),
    ])
    session.commit()

    rows = session.query(SchedulerRunLog).filter(
        SchedulerRunLog.task_name == "盯盘提醒"
    ).all()
    assert len(rows) == 1
    assert rows[0].task_name == "盯盘提醒"
