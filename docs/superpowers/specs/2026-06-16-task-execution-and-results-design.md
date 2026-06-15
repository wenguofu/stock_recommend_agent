# Task Execution & Results Pages — Design

**Date:** 2026-06-16
**Status:** Draft (pending user review)
**Scope:** Two new frontend pages + one new MySQL table + scheduler instrumentation.

## 1. Goal

Add two new pages to the stock_frontend so the user can see:

1. **What is running right now** — currently-executing tasks across both task systems
2. **What ran today (or any day in the past 7 days)** — historical execution results for both task systems

These complement the existing `/tasks` page (which is for *creating* user-defined tasks) and fill a current visibility gap: the built-in scheduler has data but no dedicated UI.

## 2. Task systems in scope

The project has two distinct task systems. Both are covered via two tabs on each new page.

| System | Source | Storage (current) |
|---|---|---|
| **A. Built-in scheduler** (8 hardcoded jobs) | [scheduler.py:451](scheduler.py#L451) | `logs/scheduler_outputs.json` (sliding 200, truncated 1000 chars) |
| **B. User-defined tasks** (price_alert, ai_analysis) | [api_routes.py:1098](api_routes.py#L1098) | `task_logs` MySQL table (full output, persistent) |

## 3. Data model

### 3.1 New table: `scheduler_run_log`

Persists every execution of a built-in scheduler task. Mirrors the shape of `task_logs` for consistency.

```python
# models.py — new
class SchedulerRunLog(Base):
    """内置调度器执行日志表"""
    __tablename__ = 'scheduler_run_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(100), nullable=False, index=True)
    task_type = Column(String(20))              # 'interval' | 'cron'
    schedule = Column(String(50))               # '300s' | '0 9 * * 1-5'
    status = Column(String(20), nullable=False) # 'running' | 'success' | 'failed' | 'skipped'
    output = Column(Text)                       # full output, no truncation
    error = Column(Text)                        # exception text
    started_at = Column(DateTime, nullable=False, index=True)
    finished_at = Column(DateTime)
    duration_ms = Column(Integer)               # (finished_at - started_at) * 1000
    trigger_source = Column(String(20))         # 'auto' | 'manual'
```

Indexes:
- `(started_at)` for date-range queries
- `(task_name, started_at)` for per-task daily views

Migration: piggyback on the existing `init_db()` / SQL bootstrap path. The new model is auto-created on app start (matches `task_logs` lifecycle).

### 3.2 No changes to existing tables

- `task_logs` — already has `started_at`, `finished_at`, `status`, `result` for user-defined tasks. No change.
- `monitor_tasks` — no change.

## 4. Backend changes

### 4.1 `scheduler.py` — instrument `_run_task()`

Add a helper next to existing `_save_output()`:

```python
def _save_run_log(self, task, started_at, status, output, error, trigger_source):
    """Persist one SchedulerRunLog row."""
    finished_at = datetime.now()
    db = SessionLocal()
    try:
        row = SchedulerRunLog(
            task_name=task['name'],
            task_type=task['type'],
            schedule=str(task.get('interval', '')) if task['type'] == 'interval' else task.get('cron', ''),
            status=status,
            output=(output or '')[:10000],  # hard cap, not the old 1000
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

`_run_task()` flow changes:
- Add a `trigger_source` parameter to `_run_task(self, task, trigger_source='auto')`:
  - `'auto'` for the main loop (`_loop` callsite)
  - `'auto'` for the catchup path (`_catchup_missed_cron` callsite — system-initiated replay, classified as auto)
  - `'manual'` for `run_task(name_or_index)` callsite (called by `POST /api/scheduler/trigger`)
- At entry, insert a row with `status='running'`, capture `log_id`
- In the `try` success branch: update the row → `status='success'`, `output=...`
- In the `except` branch: update → `status='failed'`, `error=...`
- If the task is skipped because of in-flight (returns False at the lock check), do **not** write a row (no execution happened)

`_save_output()` to `logs/scheduler_outputs.json` is **kept as a compat shim** for the existing `GET /api/scheduler/logs` endpoint. It now only writes if the legacy endpoint is still consumed elsewhere (it isn't, but we keep the file from being deleted out from under callers). Truncation is relaxed to 2000 chars.

### 4.2 `scheduler_routes.py` — extend and add

```python
@app.route("/api/scheduler/runs", methods=["GET"])
def scheduler_runs():
    """列出某天的执行记录 (用于执行结果页 Tab 1)"""
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    task = request.args.get("task", "")
    limit = int(request.args.get("limit", 200))
    db = SessionLocal()
    try:
        q = db.query(SchedulerRunLog).filter(
            SchedulerRunLog.started_at >= f"{date_str} 00:00:00",
            SchedulerRunLog.started_at <  f"{date_str} 23:59:59",
        )
        if task:
            q = q.filter(SchedulerRunLog.task_name == task)
        rows = q.order_by(SchedulerRunLog.started_at.desc()).limit(limit).all()
        return {"success": True, "data": [_serialize(r) for r in rows]}
    finally:
        db.close()

@app.route("/api/scheduler/runs/<int:run_id>", methods=["GET"])
def scheduler_run_detail(run_id):
    db = SessionLocal()
    try:
        row = db.query(SchedulerRunLog).get(run_id)
        if not row:
            return {"success": False, "error": "not found"}, 404
        return {"success": True, "data": _serialize(row)}
    finally:
        db.close()
```

`GET /api/scheduler/status` extended to expose in-flight state:

```python
def get_status(self):
    return [{
        'name': t['name'],
        'type': t['type'],
        'schedule': ...,
        'run_count': t['run_count'],
        'last_run': ...,
        'last_output': t['last_output'][:200] if t['last_output'] else '',
        'last_error': t['last_error'],
        # NEW:
        'in_flight': bool(t.get('_in_flight')),
        'current_started_at': t.get('_current_started_at'),  # ISO string or None
    } for t in self.tasks]
```

### 4.3 `api_routes.py` — `list_task_logs` extension

Add `date` filter to existing `GET /api/tasks/<id>/logs`:

```python
@app.route("/api/tasks/<int:task_id>/logs", methods=["GET"])
def list_task_logs(task_id):
    db = SessionLocal()
    try:
        date_str = request.args.get("date", "")
        limit = int(request.args.get("limit", 20))
        q = db.query(TaskLog).filter(TaskLog.task_id == task_id)
        if date_str:
            q = q.filter(
                TaskLog.started_at >= f"{date_str} 00:00:00",
                TaskLog.started_at <  f"{date_str} 23:59:59",
            )
        logs = q.order_by(TaskLog.started_at.desc()).limit(limit).all()
        return ...
```

## 5. Frontend changes

### 5.1 New pages

| File | Route | Purpose |
|---|---|---|
| `stock_frontend/src/pages/TaskExecution.tsx` | `/task-execution` | Real-time currently-executing tasks |
| `stock_frontend/src/pages/TaskResults.tsx` | `/task-results` | Historical results (date picker) |

### 5.2 `TaskExecution.tsx`

- Header: 任务标题 + `🔄 刷新` button (manual, **no auto-refresh** per user choice)
- Two tabs:
  - **内置调度器 (8)**: cards listing each of the 8 jobs. Card fields: name, type, schedule, status badge (`⏸空闲` gray / `🟢执行中` green), current elapsed time when running (computed from `current_started_at`), `last_run`, `last_output` (truncated 200). Top summary: `执行中: X / 空闲: Y / 今日已执行: Z`.
  - **用户任务 (N)**: list from `/api/tasks`, showing name, type, enabled toggle, last run, last result. No `_in_flight` exposed by B, so just show last-run state.
- Data sources: `GET /api/scheduler/status` (Tab 1) + `GET /api/tasks` (Tab 2). No new endpoints needed for Tab 2.

### 5.3 `TaskResults.tsx`

- Header: 任务执行结果 + `📅 日期选择器` (AntD `DatePicker`, default today, **disabled dates outside past 7 days**, no future dates).
- Two tabs:
  - **内置调度器历史 (今日 X 次)**: table from `GET /api/scheduler/runs?date=YYYY-MM-DD`. Columns: task_name, started_at, duration_ms, status (color tag), trigger_source. Row click → drawer/modal with full output + error.
  - **用户任务历史 (今日 X 次)**: table from `GET /api/tasks/<id>/logs?date=YYYY-MM-DD` per task. Columns: task_name, started_at, finished_at, status, triggered_count. Row click → drawer with full `result` JSON.

### 5.4 `App.tsx` and `Layout.tsx`

- Add two routes:
  ```tsx
  <Route path="/task-execution" element={<TaskExecution />} />
  <Route path="/task-results"   element={<TaskResults />} />
  ```
- Add two sidebar entries in `Layout.tsx` `QUANT_NAV`:
  ```ts
  { path: '/task-execution', label: '任务执行', icon: <PlayCircleOutlined /> },
  { path: '/task-results',   label: '任务结果', icon: <HistoryOutlined /> },
  ```

### 5.5 `services/api.ts`

Add typed wrappers:
```ts
schedulerStatus: () => GET('/api/scheduler/status'),
schedulerRuns:  (date, task?, limit=200) => GET(`/api/scheduler/runs?date=${date}&task=${task||''}&limit=${limit}`),
schedulerRunDetail: (id) => GET(`/api/scheduler/runs/${id}`),
taskLogsByDate: (taskId, date, limit=200) => GET(`/api/tasks/${taskId}/logs?date=${date}&limit=${limit}`),
```

## 6. Error handling

- Backend: missing/invalid `date` → return today's data with a 200 + warning header (don't 500).
- Backend: unknown `run_id` → 404.
- Frontend: empty state when no rows for the date; error toast on API failure.
- Frontend: date picker disables future dates (no point querying tomorrow).

## 7. Testing

TDD order — each step is a red→green cycle, `pytest -q --no-cov` between.

1. `tests/test_scheduler_run_log.py` — model insert/query, date filter, task filter, status transitions
2. `tests/test_scheduler_save_run_log.py` — `_save_run_log` called on start + finish, captures full output, no truncation under 10k
3. `tests/test_scheduler_status_in_flight.py` — `/api/scheduler/status` exposes `in_flight` + `current_started_at`
4. `tests/test_scheduler_runs_api.py` — `GET /api/scheduler/runs` date + task filter, `/runs/<id>` detail
5. `tests/test_task_logs_date_filter.py` — `list_task_logs` accepts `date` param
6. `tests/test_task_execution_page.py` (frontend) — renders, refresh button triggers refetch
7. `tests/test_task_results_page.py` (frontend) — renders, date change triggers refetch, expand shows output

## 8. Tasks list (preview, will be in `openspec/changes/task-execution-and-results/tasks.md`)

- [ ] 1. Add `SchedulerRunLog` model
- [ ] 2. Add `_save_run_log()` helper, wire into `_run_task()`
- [ ] 3. Extend `get_status()` to expose `in_flight` + `current_started_at`
- [ ] 4. Add `GET /api/scheduler/runs` and `/runs/<id>`
- [ ] 5. Extend `list_task_logs` to accept `date` filter
- [ ] 6. Add `TaskExecution.tsx` + route + sidebar
- [ ] 7. Add `TaskResults.tsx` + route + sidebar
- [ ] 8. Add typed API wrappers in `services/api.ts`
- [ ] 9. Run full test suite, `openspec validate --strict`, archive change

## 9. Out of scope (explicit YAGNI)

- No WebSocket / SSE push for live updates. Refresh button only.
- No retention policy / auto-purge of `scheduler_run_log`. It grows linearly (~14 rows/day for the 8 builtin jobs at most). At 100 bytes/row that's ~50KB/year — not a concern.
- No charts / aggregations on the results page. Plain table.
- No "retry" or "re-run" button on the results page. Existing `POST /api/scheduler/trigger` is unchanged.
- No migration of legacy `logs/scheduler_outputs.json` data into the new table. Old data is lost on the rollout boundary.
