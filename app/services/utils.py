"""Shared helpers for time handling and document serialisation."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from bson import ObjectId

from app.config import settings


def utcnow() -> datetime:
    """Timezone-aware current time in UTC."""
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    """Normalise any datetime to a timezone-aware UTC value.

    Naive datetimes are assumed to already be UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _local_zone() -> ZoneInfo | timezone:
    try:
        return ZoneInfo(settings.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def work_date_str(punch_in: datetime) -> str:
    """Business work-date (YYYY-MM-DD) in the configured local timezone."""
    local = ensure_utc(punch_in).astimezone(_local_zone())
    return local.strftime("%Y-%m-%d")


def is_late(punch_in: datetime) -> bool:
    """Return True if the punch-in is after the allowed start time + grace."""
    local = ensure_utc(punch_in).astimezone(_local_zone())
    threshold = local.replace(
        hour=settings.work_start_hour,
        minute=settings.work_start_minute,
        second=0,
        microsecond=0,
    ) + timedelta(minutes=settings.late_grace_minutes)
    return local > threshold


def worked_minutes(punch_in: datetime, punch_out: datetime) -> int:
    delta = ensure_utc(punch_out) - ensure_utc(punch_in)
    return int(delta.total_seconds() // 60)


def serialize(doc: dict) -> dict:
    """Convert a Mongo document into a JSON-friendly dict.

    Renames ``_id`` to ``id`` and stringifies ObjectId values.
    """
    out = dict(doc)
    if "_id" in out:
        out["id"] = str(out.pop("_id"))
    for key, value in out.items():
        if isinstance(value, ObjectId):
            out[key] = str(value)
    return out
