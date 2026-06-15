"""测试 GET /api/scheduler/runs 与 /runs/<id>"""
import os
import sys
import json
import pytest
from datetime import datetime
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client(mysql_test_schema, monkeypatch):
    """flask test client with SessionLocal rebound to test schema"""
    from flask import Flask
    from scheduler_routes import register_scheduler_routes
    import models

    # rebind SessionLocal to test schema
    TestSession = sessionmaker(bind=mysql_test_schema)
    monkeypatch.setattr(models, "SessionLocal", TestSession)

    app = Flask(__name__)
    app.config["TESTING"] = True
    register_scheduler_routes(app)
    with app.test_client() as c:
        yield c


def _seed(db, rows):
    from models import SchedulerRunLog
    for r in rows:
        db.add(SchedulerRunLog(**r))
    db.commit()


def test_runs_returns_today_by_default(client, mysql_test_schema):
    from models import SessionLocal
    db = SessionLocal()
    try:
        _seed(db, [
            {
                "task_name": "板块更新", "status": "success",
                "started_at": datetime.now(), "trigger_source": "auto",
            },
            {
                "task_name": "全A股刷新", "status": "failed",
                "started_at": datetime.now(), "trigger_source": "manual",
                "error": "kaboom",
            },
        ])
    finally:
        db.close()

    resp = client.get("/api/scheduler/runs")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert len(data["data"]) == 2


def test_runs_filters_by_date(client, mysql_test_schema):
    from datetime import timedelta
    from models import SessionLocal
    db = SessionLocal()
    try:
        _seed(db, [
            {
                "task_name": "板块更新", "status": "success",
                "started_at": datetime.now(), "trigger_source": "auto",
            },
            {
                "task_name": "板块更新", "status": "success",
                "started_at": datetime.now() - timedelta(days=2),
                "trigger_source": "auto",
            },
        ])
    finally:
        db.close()

    today = datetime.now().strftime("%Y-%m-%d")
    resp = client.get(f"/api/scheduler/runs?date={today}")
    data = resp.get_json()
    assert len(data["data"]) == 1


def test_runs_filters_by_task(client, mysql_test_schema):
    from models import SessionLocal
    db = SessionLocal()
    try:
        _seed(db, [
            {"task_name": "板块更新", "status": "success",
             "started_at": datetime.now(), "trigger_source": "auto"},
            {"task_name": "盯盘提醒", "status": "success",
             "started_at": datetime.now(), "trigger_source": "auto"},
        ])
    finally:
        db.close()

    resp = client.get("/api/scheduler/runs?task=盯盘提醒")
    data = resp.get_json()
    assert len(data["data"]) == 1
    assert data["data"][0]["task_name"] == "盯盘提醒"


def test_runs_detail_returns_single_row(client, mysql_test_schema):
    from models import SchedulerRunLog, SessionLocal
    db = SessionLocal()
    try:
        row = SchedulerRunLog(
            task_name="板块更新", status="success", output="full output here",
            started_at=datetime.now(), trigger_source="auto",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        rid = row.id
    finally:
        db.close()

    resp = client.get(f"/api/scheduler/runs/{rid}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["data"]["task_name"] == "板块更新"
    assert data["data"]["output"] == "full output here"


def test_runs_detail_404_for_unknown_id(client, mysql_test_schema):
    resp = client.get("/api/scheduler/runs/99999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["success"] is False
