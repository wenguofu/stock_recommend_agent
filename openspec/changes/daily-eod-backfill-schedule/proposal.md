## Why

After fixing the daily_kline_gap bug in `daily_refresh()`, the system now
correctly backfills missing trading days. But the only scheduled run is at
**10:00 weekdays** (`task_daily_prefetch` with cron `0 10 * * 1-5`), which fires
**before market close (15:00)** and uses partial / pre-close data.

Two issues with the 10:00-only schedule:
1. The 10:00 run captures the *current* trading session's morning data, missing
   the full afternoon + close price.
2. If the 10:00 run fails (timeout / scheduler hiccup), there's no fallback to
   pick up the EOD data the same day.

A second run at **21:00 weekdays** runs ~6 hours after market close, ensuring
the DB has the final EOD bars for every trading day.

## What Changes

- Add new scheduler entry `全A股日线盘后补齐` with cron `0 21 * * 1-5`,
  re-using the existing `task_daily_prefetch` function. Same code path —
  benefits from all the prior fixes (断点续传, 跳过已最新, 全记录保存,
  7-day skip threshold).
- Keep the existing 10:00 entry unchanged.
- (One-off) Run a serial backfill of all 5528 stocks to clear accumulated gaps
  from before the fix landed.

## Capabilities

### New Capabilities
- (none — pure schedule addition; no spec-level requirement change)

### Modified Capabilities
- (none)

## Impact

- Affected code:
  - **MODIFIED**: `scheduler.py` — add one new cron entry
- APIs: none
- Dependencies: none
- Daily run time: ~10 minutes (most stocks skip after first day of clean data)
- One-off backfill: ~10 minutes serial (5528 stocks, 0.1s rate limit)