"""Tests for analytics aggregation pipelines."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services import analytics_service as analytics
from app.services import attendance_service as svc


def _dt(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=timezone.utc)


async def _full_day(db, employee_id: str, day: int, in_h: int, out_h: int):
    await svc.punch_in(db, employee_id, _dt(day, in_h))
    await svc.punch_out(db, employee_id, _dt(day, out_h))


async def test_employee_summary_totals(db):
    await _full_day(db, "EMP-1", 15, 9, 17)        # 480, on time
    await svc.punch_in(db, "EMP-1", _dt(16, 10))   # late
    await svc.punch_out(db, "EMP-1", _dt(16, 18))  # 480
    summary = await analytics.employee_summary(db, "EMP-1")
    assert len(summary) == 1
    row = summary[0]
    assert row["employee_id"] == "EMP-1"
    assert row["days_present"] == 2
    assert row["total_worked_minutes"] == 960
    assert row["average_worked_minutes"] == 480.0
    assert row["late_count"] == 1


async def test_daily_report(db):
    await _full_day(db, "EMP-1", 15, 9, 17)
    await _full_day(db, "EMP-2", 15, 9, 17)
    await _full_day(db, "EMP-1", 16, 9, 17)
    report = await analytics.daily_report(db)
    by_date = {r["work_date"]: r for r in report}
    assert by_date["2026-01-15"]["employees_present"] == 2
    assert by_date["2026-01-16"]["employees_present"] == 1
    assert by_date["2026-01-15"]["total_worked_minutes"] == 960


async def test_late_arrivals(db):
    await svc.punch_in(db, "EMP-1", _dt(15, 10))
    await svc.punch_out(db, "EMP-1", _dt(15, 18))
    await svc.punch_in(db, "EMP-1", _dt(16, 10))
    await svc.punch_out(db, "EMP-1", _dt(16, 18))
    await _full_day(db, "EMP-2", 15, 9, 17)  # on time
    late = await analytics.late_arrivals(db)
    assert late == [{"employee_id": "EMP-1", "late_count": 2}]


async def test_date_range_filter(db):
    await _full_day(db, "EMP-1", 15, 9, 17)
    await _full_day(db, "EMP-1", 20, 9, 17)
    summary = await analytics.employee_summary(
        db, "EMP-1", start_date="2026-01-18", end_date="2026-01-25"
    )
    assert summary[0]["days_present"] == 1
