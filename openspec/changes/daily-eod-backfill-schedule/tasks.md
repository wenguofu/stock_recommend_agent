## 1. Add 21:00 scheduler entry

- [x] 1.1 Add new entry `全A股日线盘后补齐` to `scheduler.py` cron list with
  `cron: '0 21 * * 1-5'` reusing the existing `task_daily_prefetch` function.

## 2. One-off full backfill

- [x] 2.1 Run `batch_prefetch_all.py --daily` once across all 5528 stocks
  serially (rate-limited, idempotent upserts) to clear accumulated gaps.

## 3. Verification

- [x] 3.1 Confirm both cron entries visible via `/api/scheduler/status`.
- [x] 3.2 Confirm `openspec validate --all --strict` passes for this change.