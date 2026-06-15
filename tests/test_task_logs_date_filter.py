"""测试 list_task_logs 的 date 过滤"""
import os
import sys
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app_with_task(mysql_test_schema, monkeypatch):
    """flask app + a seeded MonitorTask. Returns (client, task_id)"""
    from flask import Flask
    import api_routes
    import models

    # rebind SessionLocal to test schema
    TestSession = sessionmaker(bind=mysql_test_schema)
    monkeypatch.setattr(models, "SessionLocal", TestSession)

    app = Flask(__name__)
    app.config["TESTING"] = True
    api_routes.register_routes(app)

    with app.test_client() as c:
        from models import MonitorTask, SessionLocal
        db = SessionLocal()
        try:
            t = MonitorTask(
                name="蓝思盯盘", task_type="price_alert",
                codes="300433", schedule="every_15m",
                enabled=True, config={},
            )
            db.add(t)
            db.commit()
            db.refresh(t)
            yield c, t.id
        finally:
            db.close()


def test_list_task_logs_no_date_returns_all(app_with_task):
    client, tid = app_with_task
    resp = client.get(f"/api/tasks/{tid}/logs")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "data" in data


def test_list_task_logs_filters_by_date(app_with_task, mysql_test_schema):
    from models import TaskLog, SessionLocal
    from datetime import datetime, timedelta

    client, tid = app_with_task
    db = SessionLocal()
    try:
        # seed 2 logs: 1 today, 1 yesterday
        db.add(TaskLog(
            task_id=tid, task_name="蓝思盯盘", task_type="price_alert",
            status="success", started_at=datetime.now(),
        ))
        db.add(TaskLog(
            task_id=tid, task_name="蓝思盯盘", task_type="price_alert",
            status="failed", started_at=datetime.now() - timedelta(days=1),
        ))
        db.commit()
    finally:
        db.close()

    today = datetime.now().strftime("%Y-%m-%d")
    resp = client.get(f"/api/tasks/{tid}/logs?date={today}")
    data = resp.get_json()
    assert len(data["data"]) == 1
    assert data["data"][0]["status"] == "success"
