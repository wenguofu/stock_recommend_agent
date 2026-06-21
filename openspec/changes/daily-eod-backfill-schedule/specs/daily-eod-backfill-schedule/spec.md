## ADDED Requirements

### Requirement: Daily 21:00 EOD backfill task
The scheduler SHALL run the existing `task_daily_prefetch` function at 21:00
on weekdays (Mon-Fri) in addition to the existing 10:00 run.

#### Scenario: 21:00 cron fires after market close
- **WHEN** the system clock reaches 21:00 on a weekday
- **THEN** the scheduler SHALL invoke `task_daily_prefetch` which runs
  `batch_prefetch_all.py --daily` to backfill missing daily K-line data
  for all A-share stocks.

#### Scenario: Skip already-up-to-date stocks
- **WHEN** the 21:00 task runs against a stock whose `data_end >= today - 7 days`
- **THEN** the task SHALL skip that stock (no network call).

#### Scenario: 10:00 task still runs unchanged
- **WHEN** the system clock reaches 10:00 on a weekday
- **THEN** the existing `全A股每日数据刷新` task SHALL fire as before.