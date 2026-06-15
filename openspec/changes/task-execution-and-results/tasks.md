# Tasks

- [x] 1. Add `SchedulerRunLog` model
- [x] 2. Instrument `_run_task` with `_save_run_log` + `trigger_source`
- [x] 3. Expose `in_flight` + `current_started_at` in `get_status()`
- [x] 4. Add `GET /api/scheduler/runs` and `/runs/<id>` endpoints
- [x] 5. Add `date` filter to `list_task_logs`
- [x] 6. Add typed API wrappers in `services/api.ts`
- [x] 7. Add `TaskExecution` page + route + sidebar
- [x] 8. Add `TaskResults` page + route + sidebar
- [x] 9. Final verification + archive
