"""Unit tests for the attendance service (punch-in/out and corrections)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.exceptions import (
    AlreadyPunchedInError,
    InvalidCorrectionError,
    NotPunchedInError,
    RecordNotFoundError,
)
from app.services import attendance_service as svc


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 1, 15, hour, minute, tzinfo=timezone.utc)


async def test_punch_in_creates_open_session(db):
    record = await svc.punch_in(db, "EMP-1", _dt(9, 0))
    assert record["status"] == "open"
    assert record["punch_out"] is None
    assert record["work_date"] == "2026-01-15"
    assert record["is_late"] is False


async def test_punch_in_twice_raises(db):
    await svc.punch_in(db, "EMP-1", _dt(9, 0))
    with pytest.raises(AlreadyPunchedInError):
        await svc.punch_in(db, "EMP-1", _dt(10, 0))


async def test_late_flag(db):
    record = await svc.punch_in(db, "EMP-1", _dt(9, 30))
    assert record["is_late"] is True


async def test_punch_out_computes_minutes(db):
    await svc.punch_in(db, "EMP-1", _dt(9, 0))
    record = await svc.punch_out(db, "EMP-1", _dt(17, 0))
    assert record["status"] == "closed"
    assert record["worked_minutes"] == 480
    assert record["is_overtime"] is False


async def test_overtime_flag(db):
    await svc.punch_in(db, "EMP-1", _dt(9, 0))
    record = await svc.punch_out(db, "EMP-1", _dt(18, 30))
    assert record["worked_minutes"] == 570
    assert record["is_overtime"] is True


async def test_punch_out_without_session_raises(db):
    with pytest.raises(NotPunchedInError):
        await svc.punch_out(db, "EMP-1", _dt(17, 0))


async def test_punch_out_before_punch_in_raises(db):
    await svc.punch_in(db, "EMP-1", _dt(9, 0))
    with pytest.raises(InvalidCorrectionError):
        await svc.punch_out(db, "EMP-1", _dt(8, 0))


async def test_correction_updates_and_audits(db):
    await svc.punch_in(db, "EMP-1", _dt(9, 0))
    record = await svc.punch_out(db, "EMP-1", _dt(17, 0))
    attendance_id = record["id"]

    result = await svc.apply_correction(
        db,
        attendance_id,
        field="punch_out",
        new_value=_dt(18, 0),
        reason="Forgot to punch out on time",
        corrected_by="admin@corp.com",
    )
    assert result["record"]["worked_minutes"] == 540
    assert result["audit"]["field"] == "punch_out"
    assert result["audit"]["corrected_by"] == "admin@corp.com"

    audit = await svc.list_audit(db, attendance_id)
    assert len(audit) == 1


async def test_correction_invalid_order_raises(db):
    await svc.punch_in(db, "EMP-1", _dt(9, 0))
    record = await svc.punch_out(db, "EMP-1", _dt(17, 0))
    with pytest.raises(InvalidCorrectionError):
        await svc.apply_correction(
            db,
            record["id"],
            field="punch_in",
            new_value=_dt(18, 0),
            reason="bad edit",
            corrected_by="admin",
        )


async def test_correction_missing_record_raises(db):
    with pytest.raises(RecordNotFoundError):
        await svc.apply_correction(
            db,
            "000000000000000000000000",
            field="punch_in",
            new_value=_dt(9, 0),
            reason="x",
            corrected_by="admin",
        )
