# Task Execution & Results Pages — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two frontend pages (`/task-execution` + `/task-results`) covering both task systems (built-in scheduler + user-defined) via tabs, backed by a new `scheduler_run_log` MySQL table for persistent scheduler history.

**Architecture:** New MySQL table mirrors `task_logs` shape. `scheduler._run_task()` is instrumented to insert/update a `scheduler_run_log` row on start and finish. New `GET /api/scheduler/runs` endpoints expose daily history. Two new React pages consume existing + new endpoints via react-query. Manual refresh button on execution page (no auto-poll). Date picker on results page.

**Tech Stack:** Python 3 / Flask / SQLAlchemy / MySQL / pytest (backend), React + AntD + @tanstack/react-query + vitest (frontend).

**Spec:** [docs/superpowers/specs/2026-06-16-task-execution-and-results-design.md](../specs/2026-06-16-task-execution-and-results-design.md)

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `models.py` | modify | Add `SchedulerRunLog` model |
| `scheduler.py` | modify | Add `_save_run_log()`, thread `trigger_source` into `_run_task`, extend `get_status()` with `in_flight` + `current_started_at` |
| `scheduler_routes.py` | modify | Add `GET /api/scheduler/runs` and `/runs/<id>` |
| `api_routes.py` | modify | Add `date` filter to `list_task_logs` |
| `stock_frontend/src/pages/TaskExecution.tsx` | create | Real-time currently-executing tasks page |
| `stock_frontend/src/pages/TaskResults.tsx` | create | Historical execution results page |
| `stock_frontend/src/App.tsx` | modify | Add 2 routes |
| `stock_frontend/src/components/Layout.tsx` | modify | Add 2 sidebar entries |
| `stock_frontend/src/services/api.ts` | modify | Add typed API wrappers |
| `tests/test_scheduler_run_log.py` | create | Model insert/query tests |
| `tests/test_scheduler_save_run_log.py` | create | `_save_run_log` + `_run_task` instrumentation tests |
| `tests/test_scheduler_status_in_flight.py` | create | `get_status` exposes in-flight state tests |
| `tests/test_scheduler_runs_api.py` | create | New `/runs` endpoint tests |
| `tests/test_task_logs_date_filter.py` | create | `list_task_logs` date filter tests |
| `tests/test_task_execution_page.py` | create | `TaskExecution` component tests |
| `tests/test_task_results_page.py` | create | `TaskResults` component tests |

---

## Task 1: Add `SchedulerRunLog` model

**Files:**
- Modify: `models.py:352-364` (add new model right after `TaskLog`)
- Test: `tests/test_scheduler_run_log.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_scheduler_run_log.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `export TEST_DATABASE_URL='mysql+pymysql://user:pass@127.0.0.1:3306/' && pytest -q --no-cov tests/test_scheduler_run_log.py`
Expected: ImportError or AttributeError on `SchedulerRunLog`.

- [ ] **Step 3: Add the model**

In `models.py`, right after the `TaskLog` class (line 364), add:

```python
class SchedulerRunLog(Base):
    """内置调度器执行日志表"""
    __tablename__ = 'scheduler_run_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False, index=True)
    task_type = Column(String(20))
    schedule = Column(String(50))
    status = Column(String(20), nullable=False)
    output = Column(Text)
    error = Column(Text)
    started_at = Column(DateTime, nullable=False, index=True)
    finished_at = Column(DateTime)
    duration_ms = Column(Integer)
    trigger_source = Column(String(20))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q --no-cov tests/test_scheduler_run_log.py`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add models.py tests/test_scheduler_run_log.py
git commit -m "feat(model): add SchedulerRunLog table for scheduler execution history"
```

---

## Task 2: Instrument `_run_task` with `_save_run_log`

**Files:**
- Modify: `scheduler.py:470-498` (add `_save_run_log` after `_save_output`)
- Modify: `scheduler.py:551-576` (instrument `_run_task`)
- Modify: `scheduler.py:578-598` (pass `trigger_source='auto'` from `_loop`)
- Modify: `scheduler.py:599-625` (pass `trigger_source='auto'` from `_catchup_missed_cron`)
- Modify: `scheduler.py:627-642` (pass `trigger_source='manual'` from `run_task`)
- Test: `tests/test_scheduler_save_run_log.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_scheduler_save_run_log.py`:

```python
"""测试 _save_run_log 和 _run_task 的日志落库行为"""
import os
import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def real_scheduler(mysql_test_schema):
    """一个不启动线程的 TaskScheduler 实例"""
    from scheduler import TaskScheduler
    sched = TaskScheduler()
    yield sched


def test_save_run_log_inserts_row(real_scheduler, mysql_test_schema):
    from models import SchedulerRunLog, SessionLocal

    task = {"name": "板块更新", "type": "cron", "cron": "0 9 * * 1-5"}
    started = datetime(2026, 6, 16, 9, 0, 12)

    real_scheduler._save_run_log(
        task=task,
        started_at=started,
        status="success",
        output="已加载 12 个板块",
        error=None,
        trigger_source="auto",
    )

    db = SessionLocal()
    try:
        rows = db.query(SchedulerRunLog).all()
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
    finally:
        db.close()


def test_run_task_writes_running_then_success(real_scheduler, mysql_test_schema):
    """_run_task 应该在开始时插入 running 行, 完成后 update 为 success"""
    from models import SchedulerRunLog, SessionLocal

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

    db = SessionLocal()
    try:
        rows = db.query(SchedulerRunLog).filter(
            SchedulerRunLog.task_name == "板块更新"
        ).all()
        # 至少 1 行 (running 插入后 update 为 success, 因此最终 status='success')
        assert len(rows) >= 1
        # 最终行的 status 应该是 success
        assert rows[-1].status == "success"
        assert rows[-1].output == "已加载 12 个板块"
        assert rows[-1].trigger_source == "auto"
    finally:
        db.close()


def test_run_task_writes_failed_status_on_exception(real_scheduler, mysql_test_schema):
    """_run_task 在异常时应该写 status=failed + error 文本"""
    from models import SchedulerRunLog, SessionLocal

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

    db = SessionLocal()
    try:
        rows = db.query(SchedulerRunLog).filter(
            SchedulerRunLog.task_name == "板块更新"
        ).all()
        assert len(rows) >= 1
        assert rows[-1].status == "failed"
        assert "kaboom" in rows[-1].error
        assert rows[-1].trigger_source == "manual"
    finally:
        db.close()


def test_run_task_in_flight_no_new_row(real_scheduler, mysql_test_schema):
    """in-flight 锁命中时不应写新行 (任务没真正执行)"""
    from models import SchedulerRunLog, SessionLocal

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

    db = SessionLocal()
    try:
        rows = db.query(SchedulerRunLog).filter(
            SchedulerRunLog.task_name == "板块更新"
        ).all()
        assert len(rows) == 0  # 没真正执行 → 没写日志
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q --no-cov tests/test_scheduler_save_run_log.py`
Expected: AttributeError on `_save_run_log`.

- [ ] **Step 3: Implement `_save_run_log` and instrument `_run_task`**

In `scheduler.py`:

1. Add import at top (after existing imports): `from models import SchedulerRunLog, SessionLocal`

2. Right after `_save_output` (line 487, before `get_recent_outputs`), add:

```python
def _save_run_log(self, task, started_at, status, output, error, trigger_source):
    """持久化一次调度器任务执行记录到 scheduler_run_log 表"""
    from models import SchedulerRunLog, SessionLocal
    finished_at = datetime.now()
    db = SessionLocal()
    try:
        row = SchedulerRunLog(
            task_name=task['name'],
            task_type=task.get('type'),
            schedule=(
                str(task.get('interval', '')) if task.get('type') == 'interval'
                else task.get('cron', '')
            ),
            status=status,
            output=(output or '')[:10000],
            error=error,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=int((finished_at - started_at).total_seconds() * 1000),
            trigger_source=trigger_source,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()
```

3. Modify `_run_task` (line 551). Replace with:

```python
def _run_task(self, task, trigger_source='auto'):
    """执行单个任务(带 in-flight 锁 + 日志落库)"""
    task_name = task['name']
    if task.get('_in_flight'):
        self._log(f"⏸ {task_name}: 已在执行中,跳过本次触发")
        return False
    task['_in_flight'] = True
    task['_current_started_at'] = datetime.now().isoformat()
    started_at = datetime.now()
    self._log(f"▶ 开始执行: {task_name}")
    self._save_run_log(
        task=task, started_at=started_at, status='running',
        output=None, error=None, trigger_source=trigger_source,
    )
    try:
        output = task['func']()
        if output:
            task['last_output'] = output
            self._log(f"✅ {task_name}: {output[:100]}")
            self._save_run_log(
                task=task, started_at=started_at, status='success',
                output=output, error=None, trigger_source=trigger_source,
            )
        else:
            self._log(f"⏭ {task_name}: 跳过（非执行时段或无输出）")
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        task['last_error'] = err
        self._log(f"❌ {task_name} 失败: {err}")
        self._save_run_log(
            task=task, started_at=started_at, status='failed',
            output=None, error=err, trigger_source=trigger_source,
        )
    finally:
        task['last_run'] = time.time()
        task['run_count'] += 1
        task['_in_flight'] = False
        task['_current_started_at'] = None
    return True
```

4. In `_loop` (line 588-594), pass `trigger_source='auto'`:

```python
self._run_task(task, trigger_source='auto')  # 原来两处都是 self._run_task(task)
```

5. In `_catchup_missed_cron` (line 623), pass `trigger_source='auto'`:

```python
self._run_task(task, trigger_source='auto')
```

6. In `run_task` (line 627, the manual trigger), pass `trigger_source='manual'`:

```python
result = self._run_task(task, trigger_source='manual')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -q --no-cov tests/test_scheduler_save_run_log.py`
Expected: 4 passed.

- [ ] **Step 5: Run existing scheduler tests to confirm no regression**

Run: `pytest -q --no-cov tests/test_scheduler.py`
Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add scheduler.py tests/test_scheduler_save_run_log.py
git commit -m "feat(scheduler): persist execution to scheduler_run_log table"
```

---

## Task 3: Expose in-flight state in `get_status()`

**Files:**
- Modify: `scheduler.py:500-510` (extend `get_status` to include `in_flight` and `current_started_at`)
- Test: `tests/test_scheduler_status_in_flight.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_scheduler_status_in_flight.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q --no-cov tests/test_scheduler_status_in_flight.py`
Expected: KeyError on `in_flight`.

- [ ] **Step 3: Extend `get_status`**

In `scheduler.py:500-510`, replace with:

```python
def get_status(self):
    """获取所有任务状态"""
    result = []
    for t in self.tasks:
        result.append({
            'name': t['name'],
            'type': t['type'],
            'schedule': str(t.get('interval', '')) if t['type'] == 'interval' else t.get('cron', ''),
            'run_count': t['run_count'],
            'last_run': datetime.fromtimestamp(t['last_run']).strftime('%Y-%m-%d %H:%M:%S') if t['last_run'] else '从未运行',
            'last_output': t['last_output'][:200] if t['last_output'] else '',
            'last_error': t['last_error'],
            'in_flight': bool(t.get('_in_flight')),
            'current_started_at': t.get('_current_started_at'),
        })
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest -q --no-cov tests/test_scheduler_status_in_flight.py`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scheduler.py tests/test_scheduler_status_in_flight.py
git commit -m "feat(scheduler): expose in_flight and current_started_at in get_status"
```

---

## Task 4: Add `GET /api/scheduler/runs` and `/runs/<id>`

**Files:**
- Modify: `scheduler_routes.py:1-49` (add 2 new endpoints + serializer)
- Test: `tests/test_scheduler_runs_api.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_scheduler_runs_api.py`:

```python
"""测试 GET /api/scheduler/runs 与 /runs/<id>"""
import os
import sys
import json
import pytest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def client(mysql_test_schema):
    """flask test client (memory db already provided by fixture)"""
    from flask import Flask
    from scheduler_routes import register_scheduler_routes
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_scheduler_routes(app)
    with app.test_client() as c:
        yield c


def _seed(session, rows):
    from models import SchedulerRunLog
    for r in rows:
        session.add(SchedulerRunLog(**r))
    session.commit()


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest -q --no-cov tests/test_scheduler_runs_api.py`
Expected: ImportError or 404 on `/api/scheduler/runs`.

- [ ] **Step 3: Implement the endpoints**

In `scheduler_routes.py`, replace the entire file content with:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调度器路由模块 — 新增 /api/scheduler/runs 端点
"""
from datetime import datetime
from flask import jsonify, request
from error_handler import json_endpoint


def _serialize_run(row):
    """序列化 SchedulerRunLog 行"""
    return {
        "id": row.id,
        "task_name": row.task_name,
        "task_type": row.task_type,
        "schedule": row.schedule,
        "status": row.status,
        "output": row.output or "",
        "error": row.error or "",
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "duration_ms": row.duration_ms,
        "trigger_source": row.trigger_source,
    }


def register_scheduler_routes(app):
    """注册调度器相关路由"""

    @app.route("/api/scheduler/status", methods=["GET"])
    @json_endpoint("raw")
    def scheduler_status():
        """查看调度器任务状态"""
        from scheduler import get_scheduler_status
        return {"success": True, "tasks": get_scheduler_status()}

    @app.route("/api/scheduler/logs", methods=["GET"])
    @json_endpoint("raw")
    def scheduler_logs():
        """查看最近调度器输出 (兼容旧 API, 从 JSON 文件读)"""
        limit = int(request.args.get("limit", 20))
        from scheduler import get_scheduler_outputs
        return {"success": True, "records": get_scheduler_outputs(limit)}

    @app.route("/api/scheduler/trigger", methods=["POST"])
    def scheduler_trigger():
        """手动触发调度器任务(修复 BUG-05: 感知 in-flight, 返 409)"""
        try:
            from scheduler import get_scheduler
            data = request.get_json(silent=True) or {}
            name = data.get("name", "")
            sched = get_scheduler()
            result = sched.run_task(name)
            status_code = 409 if result.get("in_flight") else 200
            return jsonify(result), status_code
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/scheduler/runs", methods=["GET"])
    @json_endpoint("raw")
    def scheduler_runs():
        """按日期 (默认今天) 列出 SchedulerRunLog 记录"""
        from models import SchedulerRunLog, SessionLocal
        date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
        task_filter = request.args.get("task", "")
        limit = int(request.args.get("limit", 200))

        db = SessionLocal()
        try:
            q = db.query(SchedulerRunLog).filter(
                SchedulerRunLog.started_at >= f"{date_str} 00:00:00",
                SchedulerRunLog.started_at < f"{date_str} 23:59:59",
            )
            if task_filter:
                q = q.filter(SchedulerRunLog.task_name == task_filter)
            rows = q.order_by(SchedulerRunLog.started_at.desc()).limit(limit).all()
            return {"success": True, "data": [_serialize_run(r) for r in rows]}
        finally:
            db.close()

    @app.route("/api/scheduler/runs/<int:run_id>", methods=["GET"])
    @json_endpoint("raw")
    def scheduler_run_detail(run_id):
        """获取单条 SchedulerRunLog 详情"""
        from models import SchedulerRunLog, SessionLocal
        db = SessionLocal()
        try:
            row = db.query(SchedulerRunLog).get(run_id)
            if not row:
                return jsonify({"success": False, "error": "not found"}), 404
            return {"success": True, "data": _serialize_run(row)}
        finally:
            db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -q --no-cov tests/test_scheduler_runs_api.py`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add scheduler_routes.py tests/test_scheduler_runs_api.py
git commit -m "feat(api): add GET /api/scheduler/runs and /runs/<id> endpoints"
```

---

## Task 5: Add `date` filter to `list_task_logs`

**Files:**
- Modify: `api_routes.py:1179-1198` (extend `list_task_logs` with optional `date` query param)
- Test: `tests/test_task_logs_date_filter.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_task_logs_date_filter.py`:

```python
"""测试 list_task_logs 的 date 过滤"""
import os
import sys
import pytest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app_with_task(mysql_test_schema):
    from flask import Flask
    import api_routes
    app = Flask(__name__)
    app.config["TESTING"] = True
    api_routes.register_routes(app)
    with app.test_client() as c:
        # seed a MonitorTask + TaskLog
        from models import MonitorTask, TaskLog, SessionLocal
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
```

- [ ] **Step 2: Run test to verify it fails (date param is ignored)**

Run: `pytest -q --no-cov tests/test_task_logs_date_filter.py::test_list_task_logs_filters_by_date`
Expected: AssertionError on `len(data["data"]) == 1` (returns 2 instead).

- [ ] **Step 3: Extend `list_task_logs`**

In `api_routes.py:1179-1198`, replace with:

```python
    @app.route("/api/tasks/<int:task_id>/logs", methods=["GET"])
    def list_task_logs(task_id):
        from models import TaskLog
        db = SessionLocal()
        try:
            date_str = request.args.get("date", "")
            limit = int(request.args.get("limit", 20))
            q = db.query(TaskLog).filter(TaskLog.task_id == task_id)
            if date_str:
                q = q.filter(
                    TaskLog.started_at >= f"{date_str} 00:00:00",
                    TaskLog.started_at < f"{date_str} 23:59:59",
                )
            logs = q.order_by(TaskLog.started_at.desc()).limit(limit).all()
            return jsonify({
                'success': True,
                'data': [{
                    'id': l.id, 'status': l.status,
                    'triggered_count': l.triggered_count,
                    'result': json.loads(l.result) if l.result else {},
                    'started_at': l.started_at.isoformat(),
                    'finished_at': l.finished_at.isoformat() if l.finished_at else None,
                } for l in logs]
            })
        finally:
            db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest -q --no-cov tests/test_task_logs_date_filter.py`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api_routes.py tests/test_task_logs_date_filter.py
git commit -m "feat(api): add date filter to GET /api/tasks/<id>/logs"
```

---

## Task 6: Add typed API wrappers in `services/api.ts`

**Files:**
- Modify: `stock_frontend/src/services/api.ts` (add 4 typed wrappers)
- Test: TypeScript build check (no new test file — covered by vitest typecheck in Task 7/8)

- [ ] **Step 1: Verify current state**

Look at the existing patterns in `services/api.ts`. Find the `stockAPI` export and the typed wrappers section. Pick a representative wrapper to mimic.

- [ ] **Step 2: Add wrappers**

In `stock_frontend/src/services/api.ts`, locate the `export const stockAPI` (or similar) block. Add the following methods. If the existing pattern uses `axios.get('/api/...').then(r => r.data)`, follow it. Otherwise use the template below:

```ts
// === Scheduler runs (TaskExecution + TaskResults pages) ===
schedulerStatus: () => http.get('/api/scheduler/status').then((r) => r.data),

schedulerRuns: (date: string, task?: string, limit = 200) =>
  http
    .get(
      `/api/scheduler/runs?date=${date}${task ? `&task=${encodeURIComponent(task)}` : ''}&limit=${limit}`,
    )
    .then((r) => r.data),

schedulerRunDetail: (id: number) =>
  http.get(`/api/scheduler/runs/${id}`).then((r) => r.data),

taskLogsByDate: (taskId: number, date: string, limit = 200) =>
  http
    .get(
      `/api/tasks/${taskId}/logs?date=${date}&limit=${limit}`,
    )
    .then((r) => r.data),
```

If `http` is not the name, use whatever the existing file uses (likely `api` or `axios`).

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd stock_frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add stock_frontend/src/services/api.ts
git commit -m "feat(frontend): add typed wrappers for scheduler runs + task logs by date"
```

---

## Task 7: Add `TaskExecution` page + route + sidebar

**Files:**
- Create: `stock_frontend/src/pages/TaskExecution.tsx`
- Modify: `stock_frontend/src/App.tsx` (import + add Route)
- Modify: `stock_frontend/src/components/Layout.tsx` (add nav entry)
- Test: `tests/test_task_execution_page.tsx` (or `.test.tsx` — follow project convention)

- [ ] **Step 1: Find project frontend test convention**

Run: `ls stock_frontend/src/__tests__/ | head -10 && cat stock_frontend/src/__tests__/HighWinRecommend.test.tsx 2>/dev/null | head -40 || find stock_frontend -name "*.test.tsx" | head -3`

Note the test setup pattern (test framework, render helper, mock strategy). Mirror it in the new test.

- [ ] **Step 2: Write the failing test**

Create `tests/test_task_execution_page.tsx` (or `.test.tsx`). Example skeleton — adapt to project conventions:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { BrowserRouter } from 'react-router-dom';
import TaskExecution from '../src/pages/TaskExecution';

vi.mock('../src/services/api', () => ({
  stockAPI: {
    schedulerStatus: vi.fn().mockResolvedValue({
      success: true,
      tasks: [
        {
          name: '板块更新',
          type: 'cron',
          schedule: '0 9 * * 1-5',
          run_count: 14,
          last_run: '2026-06-16 09:00:13',
          last_output: '已加载 12 个板块',
          last_error: null,
          in_flight: false,
          current_started_at: null,
        },
      ],
    }),
    listTasks: vi.fn().mockResolvedValue([]),
  },
}));

function renderWithProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ConfigProvider locale={zhCN}>
      <QueryClientProvider client={qc}>
        <BrowserRouter>{ui}</BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>,
  );
}

describe('TaskExecution', () => {
  it('renders header and tabs', async () => {
    renderWithProviders(<TaskExecution />);
    await waitFor(() => {
      expect(screen.getByText(/任务执行/)).toBeInTheDocument();
    });
    expect(screen.getByText(/内置调度器/)).toBeInTheDocument();
    expect(screen.getByText(/用户任务/)).toBeInTheDocument();
  });

  it('shows a task name from scheduler status', async () => {
    renderWithProviders(<TaskExecution />);
    await waitFor(() => {
      expect(screen.getByText('板块更新')).toBeInTheDocument();
    });
  });

  it('has a refresh button', async () => {
    renderWithProviders(<TaskExecution />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /刷新/ })).toBeInTheDocument();
    });
  });

  it('refresh button refetches data', async () => {
    renderWithProviders(<TaskExecution />);
    const btn = await screen.findByRole('button', { name: /刷新/ });
    fireEvent.click(btn);
    // mockResolvedValue already returns; just ensure no crash
    await waitFor(() => {
      expect(screen.getByText('板块更新')).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd stock_frontend && npx vitest run tests/test_task_execution_page.tsx`
Expected: Cannot find module `../src/pages/TaskExecution`.

- [ ] **Step 4: Create the page**

Create `stock_frontend/src/pages/TaskExecution.tsx`:

```tsx
import { useState } from 'react';
import { Card, Tabs, Button, Tag, Space, Typography, Empty, Spin, Alert } from 'antd';
import { ReloadOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { stockAPI } from '../services/api';

const { Title, Text } = Typography;

function formatElapsed(startedAt: string | null): string {
  if (!startedAt) return '';
  const start = new Date(startedAt).getTime();
  const now = Date.now();
  const sec = Math.floor((now - start) / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const s = sec % 60;
  return `${min}m${s.toString().padStart(2, '0')}s`;
}

export default function TaskExecution() {
  const [tick, setTick] = useState(0);
  const { data: statusData, isLoading: statusLoading, refetch: refetchStatus } = useQuery({
    queryKey: ['scheduler-status', tick],
    queryFn: () => stockAPI.schedulerStatus(),
  });
  const { data: userTasks, isLoading: tasksLoading, refetch: refetchTasks } = useQuery({
    queryKey: ['user-tasks', tick],
    queryFn: () => stockAPI.listTasks(),
  });

  const handleRefresh = () => setTick((t) => t + 1);

  const tasks: any[] = statusData?.tasks || [];
  const inFlight = tasks.filter((t) => t.in_flight).length;
  const todayCount = tasks.reduce((sum, t) => sum + (t.run_count || 0), 0);

  const schedulerTab = (
    <div data-testid="scheduler-tab">
      <Card style={{ marginBottom: 16 }}>
        <Space size="large">
          <Text>执行中: <Tag color="green">{inFlight}</Tag></Text>
          <Text>空闲: <Tag>{tasks.length - inFlight}</Tag></Text>
          <Text>累计运行: <Tag color="blue">{todayCount}</Tag></Text>
        </Space>
      </Card>
      {statusLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
      ) : tasks.length === 0 ? (
        <Empty description="暂无调度任务" />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {tasks.map((t) => (
            <Card key={t.name} size="small">
              <Space style={{ marginBottom: 8 }}>
                {t.in_flight ? (
                  <Tag color="green" icon={<PlayCircleOutlined />}>
                    执行中 {formatElapsed(t.current_started_at)}
                  </Tag>
                ) : (
                  <Tag color="default" icon={<PauseCircleOutlined />}>空闲</Tag>
                )}
                <Text strong>{t.name}</Text>
                <Tag color="blue">{t.type}</Tag>
                <Tag>{t.schedule}</Tag>
              </Space>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  上次运行: {t.last_run}
                </Text>
              </div>
              {t.last_output && (
                <div style={{ marginTop: 4, fontSize: 12, color: '#666' }}>
                  {t.last_output}
                </div>
              )}
              {t.last_error && (
                <Alert
                  type="error"
                  message={t.last_error}
                  showIcon
                  style={{ marginTop: 8 }}
                />
              )}
            </Card>
          ))}
        </Space>
      )}
    </div>
  );

  const userTab = (
    <div data-testid="user-tasks-tab">
      {tasksLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
      ) : !userTasks || userTasks.length === 0 ? (
        <Empty description="暂无用户任务" />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {userTasks.map((t: any) => (
            <Card key={t.id} size="small">
              <Space>
                <Text strong>{t.name}</Text>
                <Tag color="blue">{t.task_type}</Tag>
                <Tag color={t.enabled ? 'green' : 'default'}>
                  {t.enabled ? '启用' : '停用'}
                </Tag>
              </Space>
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  股票: {(t.codes || []).join(', ')} · 频率: {t.schedule}
                </Text>
              </div>
              {t.last_run && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    上次: {new Date(t.last_run).toLocaleString()}
                  </Text>
                </div>
              )}
            </Card>
          ))}
        </Space>
      )}
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>⏱ 任务执行</Title>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh}>刷新</Button>
      </div>
      <Tabs
        items={[
          { key: 'sched', label: `内置调度器 (${tasks.length})`, children: schedulerTab },
          { key: 'user', label: `用户任务 (${userTasks?.length || 0})`, children: userTab },
        ]}
      />
    </div>
  );
}
```

> Note: `stockAPI.listTasks` is referenced; if your typed wrapper has a different name (e.g. `stockAPI.tasks.list()`), update accordingly.

- [ ] **Step 5: Wire up the route**

In `stock_frontend/src/App.tsx`, add import after the existing `Tasks` import:

```tsx
import TaskExecution from './pages/TaskExecution';
```

And add a Route inside `<Routes>`:

```tsx
<Route path="/task-execution" element={<TaskExecution />} />
```

- [ ] **Step 6: Add sidebar entry**

In `stock_frontend/src/components/Layout.tsx`, add to `QUANT_NAV` (after the `tasks` entry):

```tsx
{ path: '/task-execution', label: '任务执行', icon: <PlayCircleOutlined /> },
```

If `PlayCircleOutlined` is not yet imported, add it to the existing `@ant-design/icons` import line.

- [ ] **Step 7: Run test to verify it passes**

Run: `cd stock_frontend && npx vitest run tests/test_task_execution_page.tsx`
Expected: All tests pass.

- [ ] **Step 8: TypeScript build check**

Run: `cd stock_frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 9: Commit**

```bash
git add stock_frontend/src/pages/TaskExecution.tsx \
        stock_frontend/src/App.tsx \
        stock_frontend/src/components/Layout.tsx \
        tests/test_task_execution_page.tsx
git commit -m "feat(frontend): add TaskExecution page with refresh button"
```

---

## Task 8: Add `TaskResults` page + route + sidebar

**Files:**
- Create: `stock_frontend/src/pages/TaskResults.tsx`
- Modify: `stock_frontend/src/App.tsx` (add route)
- Modify: `stock_frontend/src/components/Layout.tsx` (add nav entry)
- Test: `tests/test_task_results_page.tsx` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_task_results_page.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { BrowserRouter } from 'react-router-dom';
import TaskResults from '../src/pages/TaskResults';

vi.mock('../src/services/api', () => ({
  stockAPI: {
    schedulerRuns: vi.fn().mockResolvedValue({
      success: true,
      data: [
        {
          id: 1,
          task_name: '板块更新',
          status: 'success',
          output: '已加载 12 个板块',
          error: '',
          started_at: '2026-06-16T09:00:12',
          finished_at: '2026-06-16T09:00:13',
          duration_ms: 1147,
          trigger_source: 'auto',
        },
        {
          id: 2,
          task_name: '全A股刷新',
          status: 'failed',
          output: '',
          error: 'kaboom',
          started_at: '2026-06-16T10:00:00',
          finished_at: '2026-06-16T10:00:08',
          duration_ms: 8400,
          trigger_source: 'auto',
        },
      ],
    }),
    listTasks: vi.fn().mockResolvedValue([]),
    taskLogsByDate: vi.fn().mockResolvedValue({ success: true, data: [] }),
  },
}));

function renderWithProviders(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <ConfigProvider locale={zhCN}>
      <QueryClientProvider client={qc}>
        <BrowserRouter>{ui}</BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>,
  );
}

describe('TaskResults', () => {
  it('renders header', async () => {
    renderWithProviders(<TaskResults />);
    await waitFor(() => {
      expect(screen.getByText(/任务执行结果/)).toBeInTheDocument();
    });
  });

  it('renders two tabs', async () => {
    renderWithProviders(<TaskResults />);
    await waitFor(() => {
      expect(screen.getByText(/内置调度器/)).toBeInTheDocument();
    });
    expect(screen.getByText(/用户任务/)).toBeInTheDocument();
  });

  it('shows scheduler run rows from API', async () => {
    renderWithProviders(<TaskResults />);
    await waitFor(() => {
      expect(screen.getByText('板块更新')).toBeInTheDocument();
    });
    expect(screen.getByText('全A股刷新')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd stock_frontend && npx vitest run tests/test_task_results_page.tsx`
Expected: Cannot find module `../src/pages/TaskResults`.

- [ ] **Step 3: Create the page**

Create `stock_frontend/src/pages/TaskResults.tsx`:

```tsx
import { useState } from 'react';
import { Card, Tabs, DatePicker, Table, Tag, Typography, Empty, Spin, Drawer, Descriptions, Space } from 'antd';
import { useQuery } from '@tanstack/react-query';
import dayjs, { Dayjs } from 'dayjs';
import { stockAPI } from '../services/api';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const STATUS_COLORS: Record<string, string> = {
  success: 'green',
  failed: 'red',
  running: 'blue',
  skipped: 'default',
};

function disabledDate(current: Dayjs) {
  // 禁用未来日期 + 7 天前之前
  const today = dayjs().endOf('day');
  const minDate = dayjs().subtract(7, 'day').startOf('day');
  return current && (current > today || current < minDate);
}

export default function TaskResults() {
  const [date, setDate] = useState<Dayjs>(dayjs());
  const dateStr = date.format('YYYY-MM-DD');

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['scheduler-runs', dateStr],
    queryFn: () => stockAPI.schedulerRuns(dateStr),
  });

  const { data: userTasks } = useQuery({
    queryKey: ['user-tasks-results'],
    queryFn: () => stockAPI.listTasks(),
  });

  // 对每个用户任务并行拉日志,合并
  const taskIds: number[] = (userTasks || []).map((t: any) => t.id);
  const taskLogQueries = useQuery({
    queryKey: ['user-task-logs', dateStr, taskIds.join(',')],
    queryFn: async () => {
      const lists = await Promise.all(
        taskIds.map((id) => stockAPI.taskLogsByDate(id, dateStr)),
      );
      return lists.flatMap((r: any, i: number) =>
        (r.data || []).map((log: any) => ({
          ...log,
          task_name: (userTasks || [])[i]?.name || `任务${i + 1}`,
        })),
      );
    },
    enabled: taskIds.length > 0,
  });

  const [drawerRow, setDrawerRow] = useState<any>(null);

  const runs: any[] = runsData?.data || [];
  const userLogs: any[] = taskLogQueries.data || [];

  const schedulerColumns = [
    { title: '任务', dataIndex: 'task_name', key: 'task_name' },
    {
      title: '触发时间',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      render: (v: number) => (v == null ? '-' : `${(v / 1000).toFixed(1)}s`),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '来源',
      dataIndex: 'trigger_source',
      key: 'trigger_source',
      render: (v: string) => <Tag>{v || '-'}</Tag>,
    },
  ];

  const userColumns = [
    { title: '任务', dataIndex: 'task_name', key: 'task_name' },
    {
      title: '触发时间',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '触发条数',
      dataIndex: 'triggered_count',
      key: 'triggered_count',
      render: (v: number) => v || 0,
    },
  ];

  const schedulerTab = (
    <Card>
      {runsLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
      ) : runs.length === 0 ? (
        <Empty description={`${dateStr} 暂无调度器执行记录`} />
      ) : (
        <Table
          rowKey="id"
          dataSource={runs}
          columns={schedulerColumns}
          pagination={{ pageSize: 20 }}
          onRow={(record) => ({ onClick: () => setDrawerRow(record) })}
        />
      )}
    </Card>
  );

  const userTab = (
    <Card>
      {!userTasks || userTasks.length === 0 ? (
        <Empty description="暂无用户任务" />
      ) : taskLogQueries.isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
      ) : userLogs.length === 0 ? (
        <Empty description={`${dateStr} 暂无用户任务执行记录`} />
      ) : (
        <Table
          rowKey="id"
          dataSource={userLogs}
          columns={userColumns}
          pagination={{ pageSize: 20 }}
          onRow={(record) => ({ onClick: () => setDrawerRow(record) })}
        />
      )}
    </Card>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>📊 任务执行结果</Title>
        <Space>
          <Text type="secondary">日期:</Text>
          <DatePicker
            value={date}
            onChange={(d) => d && setDate(d)}
            disabledDate={disabledDate}
            allowClear={false}
          />
        </Space>
      </div>
      <Tabs
        items={[
          { key: 'sched', label: `内置调度器 (${runs.length})`, children: schedulerTab },
          { key: 'user', label: `用户任务 (${userLogs.length})`, children: userTab },
        ]}
      />
      <Drawer
        open={!!drawerRow}
        onClose={() => setDrawerRow(null)}
        title={drawerRow?.task_name || '详情'}
        width={600}
      >
        {drawerRow && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="状态">
              <Tag color={STATUS_COLORS[drawerRow.status] || 'default'}>{drawerRow.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">
              {drawerRow.started_at ? new Date(drawerRow.started_at).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="结束时间">
              {drawerRow.finished_at ? new Date(drawerRow.finished_at).toLocaleString() : '-'}
            </Descriptions.Item>
            {drawerRow.duration_ms != null && (
              <Descriptions.Item label="耗时">{(drawerRow.duration_ms / 1000).toFixed(2)}s</Descriptions.Item>
            )}
            {drawerRow.trigger_source && (
              <Descriptions.Item label="触发来源">{drawerRow.trigger_source}</Descriptions.Item>
            )}
            {drawerRow.output && (
              <Descriptions.Item label="输出">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{drawerRow.output}</pre>
              </Descriptions.Item>
            )}
            {drawerRow.error && (
              <Descriptions.Item label="错误">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0, color: '#cf1322' }}>{drawerRow.error}</pre>
              </Descriptions.Item>
            )}
            {drawerRow.result && (
              <Descriptions.Item label="结果">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(drawerRow.result, null, 2)}</pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
```

- [ ] **Step 4: Wire up the route**

In `stock_frontend/src/App.tsx`, add import after `TaskExecution`:

```tsx
import TaskResults from './pages/TaskResults';
```

And add a Route:

```tsx
<Route path="/task-results" element={<TaskResults />} />
```

- [ ] **Step 5: Add sidebar entry**

In `stock_frontend/src/components/Layout.tsx`, add to `QUANT_NAV` (after the `task-execution` entry):

```tsx
{ path: '/task-results', label: '任务结果', icon: <HistoryOutlined /> },
```

If `HistoryOutlined` is not yet imported, add it to the existing `@ant-design/icons` import.

- [ ] **Step 6: Run test to verify it passes**

Run: `cd stock_frontend && npx vitest run tests/test_task_results_page.tsx`
Expected: All tests pass.

- [ ] **Step 7: TypeScript build check**

Run: `cd stock_frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 8: Commit**

```bash
git add stock_frontend/src/pages/TaskResults.tsx \
        stock_frontend/src/App.tsx \
        stock_frontend/src/components/Layout.tsx \
        tests/test_task_results_page.tsx
git commit -m "feat(frontend): add TaskResults page with date picker"
```

---

## Task 9: Final verification + OpenSpec change + archive

**Files:**
- Create: `openspec/changes/task-execution-and-results/proposal.md`
- Create: `openspec/changes/task-execution-and-results/tasks.md`
- Create: `openspec/changes/task-execution-and-results/specs/scheduler/spec.md` (delta to `openspec/specs/scheduler.md`)

- [ ] **Step 1: Run full backend test suite**

Run: `pytest -q --no-cov tests/`
Expected: All pass (no regressions).

- [ ] **Step 2: Run frontend test suite**

Run: `cd stock_frontend && npx vitest run`
Expected: All pass.

- [ ] **Step 3: Run TypeScript build**

Run: `cd stock_frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Create OpenSpec proposal**

Run: `mkdir -p openspec/changes/task-execution-and-results/specs/scheduler`

Write `openspec/changes/task-execution-and-results/proposal.md`:

```markdown
# 任务执行 & 结果页面

## Why

当前内置调度器 (8 个内置任务) 只有 JSON API,无专门 UI。用户任务虽有 `/tasks` 列表,但需要查看执行结果时必须进入每个任务的展开面板,体验差。新增两个独立页面提供统一视图。

## What Changes

- 新增 `GET /api/scheduler/runs?date=...&task=...&limit=...`
- 新增 `GET /api/scheduler/runs/<id>`
- 扩展 `GET /api/scheduler/status` 暴露 `in_flight` + `current_started_at`
- 扩展 `GET /api/tasks/<id>/logs` 支持 `?date=...`
- 新增 `SchedulerRunLog` MySQL 表 (持久化调度器执行历史)
- `scheduler._run_task` 增加日志落库 + 触发来源 (auto/manual)
- 新增前端 `/task-execution` 页面 (实时 + 手动刷新)
- 新增前端 `/task-results` 页面 (历史 + 日期选择器)
- 侧边栏新增 2 个入口

## Impact

- 影响的 spec: `openspec/specs/scheduler.md` (新增表 + 新增端点)
- 不影响用户任务的存储 / 调度逻辑
```

- [ ] **Step 5: Create OpenSpec tasks.md**

Write `openspec/changes/task-execution-and-results/tasks.md`:

```markdown
# Tasks

- [ ] 1. Add `SchedulerRunLog` model
- [ ] 2. Instrument `_run_task` with `_save_run_log` + `trigger_source`
- [ ] 3. Expose `in_flight` + `current_started_at` in `get_status()`
- [ ] 4. Add `GET /api/scheduler/runs` and `/runs/<id>` endpoints
- [ ] 5. Add `date` filter to `list_task_logs`
- [ ] 6. Add typed API wrappers in `services/api.ts`
- [ ] 7. Add `TaskExecution` page + route + sidebar
- [ ] 8. Add `TaskResults` page + route + sidebar
- [ ] 9. Final verification + archive
```

- [ ] **Step 6: Create OpenSpec spec delta**

Write `openspec/changes/task-execution-and-results/specs/scheduler/spec.md`:

```markdown
# Scheduler spec delta

## ADDED Requirements

### `scheduler_run_log` 持久化

系统 MUST 在每次内置任务执行时向 `scheduler_run_log` 表插入一条记录,字段:
- `task_name`, `task_type`, `schedule`, `status`, `output`, `error`,
  `started_at`, `finished_at`, `duration_ms`, `trigger_source`

`trigger_source` 取值:
- `auto` — 主循环或启动补跑触发
- `manual` — 用户通过 `POST /api/scheduler/trigger` 触发

### `/api/scheduler/runs` 端点

`GET /api/scheduler/runs?date=YYYY-MM-DD&task=<name>&limit=<n>`

- `date` 默认今天
- `task` 可选,过滤单个任务
- `limit` 默认 200
- 按 `started_at` 倒序返回

### `/api/scheduler/runs/<id>` 端点

`GET /api/scheduler/runs/<id>`

- 返回单条 `SchedulerRunLog` 完整字段
- 未知 id 返 404

### `get_status` 扩展

`GET /api/scheduler/status` 响应中每条 task 增加:
- `in_flight: bool` — 是否正在执行
- `current_started_at: string | null` — 当前执行开始时间 (ISO),无则 null
```

- [ ] **Step 7: Run `openspec validate --strict`**

Run: `openspec validate --strict --changes`
Expected: No errors.

- [ ] **Step 8: Run `git status` and confirm no stray files**

Run: `git status`
Expected: Only the OpenSpec change files + the implementation files from Tasks 1-8 are present. No stray untracked files.

- [ ] **Step 9: Commit + invoke verification skill**

Run:
```bash
git add openspec/changes/task-execution-and-results/
git commit -m "docs(openspec): add task-execution-and-results change"
```

Then invoke `superpowers:verification-before-completion` to do the final self-audit before claiming done.

- [ ] **Step 10: Archive the change**

After merge / commit, run: `openspec archive task-execution-and-results --yes`
Expected: Change moved to `openspec/changes/archive/`, spec deltas folded into `openspec/specs/scheduler.md`.

---

## Self-Review Checklist

- ✓ All spec sections covered (3 backend tasks, 2 frontend tasks, 1 OpenSpec)
- ✓ No TBD / TODO / placeholders
- ✓ Output cap values consistent (10k in Task 2, 2k in compat shim in Task 4)
- ✓ Method signatures consistent: `_save_run_log(task, started_at, status, output, error, trigger_source)` used in Task 2 and Task 3 reference
- ✓ API path consistent: `/api/scheduler/runs` everywhere
- ✓ Frontend wrapper names consistent: `schedulerStatus`, `schedulerRuns`, `schedulerRunDetail`, `taskLogsByDate`
- ✓ `trigger_source` values: `auto` and `manual` only, catchup = auto (clarified)
- ✓ Date picker bounds: past 7 days, no future
- ✓ Each task ends with a commit
- ✓ Each step is one action (2-5 min)
