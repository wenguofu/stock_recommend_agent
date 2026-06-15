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
