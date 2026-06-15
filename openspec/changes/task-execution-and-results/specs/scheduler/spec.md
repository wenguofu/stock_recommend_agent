# Scheduler spec delta

## ADDED Requirements

### Requirement: scheduler_run_log 持久化

系统 MUST 在每次内置任务执行时向 `scheduler_run_log` 表插入一条记录,字段:
- `task_name`, `task_type`, `schedule`, `status`, `output`, `error`,
  `started_at`, `finished_at`, `duration_ms`, `trigger_source`

#### Scenario: 主循环触发执行

- **WHEN** 调度器主循环触发某内置任务执行
- **THEN** 任务结束后 MUST 插入一条 `scheduler_run_log` 记录, `trigger_source = 'auto'`, `started_at` / `finished_at` / `duration_ms` 正确填写

#### Scenario: 手动触发执行

- **WHEN** 用户通过 `POST /api/scheduler/trigger` 触发某内置任务
- **THEN** 任务结束后 MUST 插入一条 `scheduler_run_log` 记录, `trigger_source = 'manual'`

### Requirement: /api/scheduler/runs 端点

系统 MUST 提供 `GET /api/scheduler/runs?date=YYYY-MM-DD&task=<name>&limit=<n>` 端点。

#### Scenario: 默认查询当天全部

- **WHEN** 调用 `GET /api/scheduler/runs` 无任何参数
- **THEN** 返回 `date` 为今天的所有 `SchedulerRunLog` 记录, 按 `started_at` 倒序, 最多 200 条

#### Scenario: 按日期过滤

- **WHEN** 调用 `GET /api/scheduler/runs?date=2026-06-15`
- **THEN** 仅返回 `started_at` 落在 2026-06-15 当天 (本地时区) 的记录

#### Scenario: 按任务名过滤

- **WHEN** 调用 `GET /api/scheduler/runs?task=portfolio_sync`
- **THEN** 仅返回 `task_name = 'portfolio_sync'` 的记录

#### Scenario: limit 上限

- **WHEN** 调用 `GET /api/scheduler/runs?limit=10`
- **THEN** 最多返回 10 条记录, 按 `started_at` 倒序

### Requirement: /api/scheduler/runs/<id> 端点

系统 MUST 提供 `GET /api/scheduler/runs/<id>` 端点。

#### Scenario: 已知 id

- **WHEN** 调用 `GET /api/scheduler/runs/<已知整数 id>`
- **THEN** 返回该条 `SchedulerRunLog` 完整 JSON

#### Scenario: 未知 id

- **WHEN** 调用 `GET /api/scheduler/runs/<不存在的 id>`
- **THEN** 响应 HTTP 404

### Requirement: get_status 扩展

`GET /api/scheduler/status` 响应中每条 task MUST 增加两个字段:
- `in_flight: bool` — 是否正在执行
- `current_started_at: string | null` — 当前执行开始时间 (ISO 8601), 无则 null

#### Scenario: 任务空闲时

- **WHEN** 某内置任务未在执行
- **THEN** 该 task 条目 MUST 包含 `in_flight = false`, `current_started_at = null`

#### Scenario: 任务执行中

- **WHEN** 某内置任务正在被 `_run_task` 执行
- **THEN** 该 task 条目 MUST 包含 `in_flight = true`, `current_started_at` 为当前执行开始时间 (ISO)
