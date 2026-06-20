"""
Regression test for the daily_kline_gap bug.

Bug: `batch_prefetch_all.daily_refresh()` previously called
`fetch_stock_data(code, name, days=5)` which returns up to 5 records, but
the function only saved `records[-1]` (latest one). Result: any day when
fetch_stock_data returned N>1 records, the intermediate N-1 dates were
silently dropped, leaving gaps that accumulated over time.

Fix: daily_refresh now saves the full `records` list, not just `latest`.

Tests:
1. AST inspection: verify the source calls save_backtest_data_batch with
   `records`, not `[latest]`.
2. Threshold: verify the skip threshold covers weekends (7 days), not just
   literal yesterday.
3. End-to-end: run daily_refresh against a controlled DB row and verify
   all 5 mock records are persisted, not just the latest.
"""
import inspect
import os
import sys
import pytest


def _read_daily_refresh_source() -> str:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from batch_prefetch_all import daily_refresh
    return inspect.getsource(daily_refresh)


def test_daily_refresh_saves_full_records_list():
    """The bug: only `records[-1]` was being saved. Fix: save full `records`."""
    src = _read_daily_refresh_source()

    # The buggy form: save_backtest_data_batch(... [latest])
    assert "[latest])" not in src, (
        "REGRESSION: daily_refresh still saves only the latest record "
        "(`save_backtest_data_batch(..., [latest])`). This causes gaps."
    )

    # The fix: save the full records list
    assert "save_backtest_data_batch(session, s[\"code\"], records)" in src, (
        "daily_refresh must call save_backtest_data_batch with the full "
        "`records` list, not just the latest."
    )


def test_skip_threshold_covers_weekends():
    """Threshold must be today - 7 days (covers weekends/holidays), not today - 1."""
    src = _read_daily_refresh_source()

    assert "skip_threshold_str" in src, (
        "REGRESSION: daily_refresh lost the 7-day skip threshold. "
        "Without it, weekend/holiday runs see 'yesterday' as Saturday/Sunday, "
        "Sina API only returns the previous trading day, and ALL stocks fail."
    )
    assert "days=7" in src, (
        "Skip threshold must be 7 days to cover weekends + 1-day holidays."
    )


def test_meta_updated_with_full_record_range():
    """Meta should reflect min(records[0].date) and max(records[-1].date),
    not just latest."""
    src = _read_daily_refresh_source()

    # Check that meta start uses records[0] (not just latest)
    assert "records[0][\"date\"]" in src, (
        "meta.data_start should use records[0]['date'] for full range coverage"
    )
    assert "records[-1][\"date\"]" in src, (
        "meta.data_end should use records[-1]['date'] for full range coverage"
    )


def test_end_to_end_backfill_persists_all_records():
    """Verify the save path via a real-DB integration check.

    daily_refresh uses lazy `from db import ...` inside the hot loop, which
    makes mocking fragile. Instead, we run daily_refresh end-to-end against
    a small synthetic stock and assert the DB row count grew from 0 to N.
    """
    from sqlalchemy import create_engine, text
    from datetime import date, timedelta

    db_url = os.environ.get("DATABASE_URL") or \
        "mysql+pymysql://root:@localhost:3306/stock_trading?charset=utf8mb4"
    eng = create_engine(db_url)

    test_code = "999888"  # synthetic; safe to add/cleanup
    test_name = "TEST_BACKFILL"

    # Cleanup any prior run
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM backtest_data WHERE code = :c"), {"c": test_code})
        conn.execute(text("DELETE FROM backtest_stock_meta WHERE code = :c"), {"c": test_code})

    # Build 5 fake records spanning a recent 7-day window so they pass
    # the skip threshold check. Records must be sorted ASCENDING by date
    # to match the actual fetch_stock_data output shape.
    from datetime import datetime, date as _date, timedelta as _td
    today = _date.today()
    fake_records = []
    # Generate oldest-first (day 5 ago to day 1 ago) so the list is ASCENDING
    for i in range(5, 0, -1):  # 5..1 days ago
        d = (today - _td(days=i)).isoformat()
        fake_records.append({
            "date": d, "open": 10.0, "close": 10.5, "high": 10.8, "low": 9.9,
            "volume": 1000, "amount": 10500, "change_pct": 0.5,
            "turnover": 1.0, "source": "sina",
        })
    assert fake_records[0]["date"] < fake_records[-1]["date"]

    # Inject the fake stock into get_all_stocks and fetch_stock_data,
    # and use the real save_backtest_data_batch / save_backtest_meta.
    from unittest.mock import patch
    from batch_prefetch_all import daily_refresh

    with patch("batch_prefetch_all.get_all_stocks",
               return_value=[{"code": test_code, "name": test_name}]), \
         patch("batch_prefetch_all.fetch_stock_data", return_value=fake_records), \
         patch("batch_prefetch_all.get_db_completed_with_data_after", return_value=set()), \
         patch("batch_prefetch_all.load_progress",
               return_value={"completed": [], "failed": []}):

        daily_refresh(max_workers=2, max_minutes=1)

    # Verify DB state
    with eng.begin() as conn:
        rows = list(conn.execute(text(
            "SELECT date FROM backtest_data WHERE code = :c ORDER BY date"
        ), {"c": test_code}).fetchall())
        meta = conn.execute(text(
            "SELECT data_start, data_end, total_days FROM backtest_stock_meta "
            "WHERE code = :c"
        ), {"c": test_code}).fetchone()

    # Cleanup
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM backtest_data WHERE code = :c"), {"c": test_code})
        conn.execute(text("DELETE FROM backtest_stock_meta WHERE code = :c"), {"c": test_code})

    assert len(rows) == len(fake_records), (
        f"BUG NOT FIXED: expected {len(fake_records)} DB rows for synthetic "
        f"stock {test_code}, got {len(rows)}. The daily_refresh must save "
        f"ALL fetched records, not just the latest."
    )
    saved_dates = sorted(r[0] for r in rows)
    expected_dates = sorted(r["date"] for r in fake_records)
    assert saved_dates == expected_dates, (
        f"Date mismatch: missing {set(expected_dates) - set(saved_dates)}"
    )
    if meta is not None:
        assert meta[0] <= fake_records[0]["date"] <= meta[1], (
            f"meta range {meta[0]}..{meta[1]} doesn't cover records"
        )