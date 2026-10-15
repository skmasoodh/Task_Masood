"""Core attendance business logic: punch-in, punch-out and corrections."""
from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import settings
from app.database import ATTENDANCE_COLLECTION, AUDIT_COLLECTION
from app.exceptions import (
    AlreadyPunchedInError,
    InvalidCorrectionError,
    NotPunchedInError,
    RecordNotFoundError,
)
from app.schemas.attendance import SessionStatus
from app.services import utils


def _to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError) as exc:
        raise RecordNotFoundError(f"Invalid id: {value!r}") from exc


async def punch_in(
    db: AsyncIOMotorDatabase,
    employee_id: str,
    timestamp: datetime | None = None,
) -> dict:
    """Open a new attendance session for an employee.

    Business rule: an employee may not punch in while an open session exists.
    """
    coll = db[ATTENDANCE_COLLECTION]

    existing = await coll.find_one(
        {"employee_id": employee_id, "status": SessionStatus.OPEN.value}
    )
    if existing is not None:
        raise AlreadyPunchedInError(
            f"Employee {employee_id} already has an open session."
        )

    punch_time = utils.ensure_utc(timestamp) if timestamp else utils.utcnow()
    now = utils.utcnow()
    doc = {
        "employee_id": employee_id,
        "work_date": utils.work_date_str(punch_time),
        "punch_in": punch_time,
        "punch_out": None,
        "status": SessionStatus.OPEN.value,
        "worked_minutes": None,
        "is_late": utils.is_late(punch_time),
        "is_overtime": False,
        "created_at": now,
        "updated_at": now,
    }
    result = await coll.insert_one(doc)
    doc["_id"] = result.inserted_id
    return utils.serialize(doc)


async def punch_out(
    db: AsyncIOMotorDatabase,
    employee_id: str,
    timestamp: datetime | None = None,
) -> dict:
    """Close the employee's open session and compute worked minutes.

    Business rule: an employee must have an open session to punch out, and the
    punch-out time must not precede the punch-in time.
    """
    coll = db[ATTENDANCE_COLLECTION]

    session = await coll.find_one(
        {"employee_id": employee_id, "status": SessionStatus.OPEN.value}
    )
    if session is None:
        raise NotPunchedInError(
            f"Employee {employee_id} has no open session to punch out."
        )

    punch_time = utils.ensure_utc(timestamp) if timestamp else utils.utcnow()
    if punch_time < utils.ensure_utc(session["punch_in"]):
        raise InvalidCorrectionError(
            "Punch-out time cannot be earlier than punch-in time."
        )

    minutes = utils.worked_minutes(session["punch_in"], punch_time)
    update = {
        "punch_out": punch_time,
        "status": SessionStatus.CLOSED.value,
        "worked_minutes": minutes,
        "is_overtime": minutes > settings.standard_work_minutes,
        "updated_at": utils.utcnow(),
    }
    await coll.update_one({"_id": session["_id"]}, {"$set": update})
    session.update(update)
    return utils.serialize(session)


async def get_record(db: AsyncIOMotorDatabase, attendance_id: str) -> dict:
    coll = db[ATTENDANCE_COLLECTION]
    doc = await coll.find_one({"_id": _to_object_id(attendance_id)})
    if doc is None:
        raise RecordNotFoundError(f"Attendance record {attendance_id} not found.")
    return utils.serialize(doc)


async def list_records(
    db: AsyncIOMotorDatabase,
    employee_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query: dict = {}
    if employee_id:
        query["employee_id"] = employee_id
    cursor = db[ATTENDANCE_COLLECTION].find(query).sort("punch_in", -1).limit(limit)
    return [utils.serialize(doc) async for doc in cursor]


async def apply_correction(
    db: AsyncIOMotorDatabase,
    attendance_id: str,
    field: str,
    new_value: datetime,
    reason: str,
    corrected_by: str,
) -> dict:
    """Apply a manual correction to a punch time and record an audit entry.

    Recomputes derived fields (worked minutes, late/overtime flags) and writes
    an immutable audit document capturing the old and new values.
    """
    coll = db[ATTENDANCE_COLLECTION]
    oid = _to_object_id(attendance_id)
    record = await coll.find_one({"_id": oid})
    if record is None:
        raise RecordNotFoundError(f"Attendance record {attendance_id} not found.")

    if field not in ("punch_in", "punch_out"):
        raise InvalidCorrectionError(f"Field {field!r} cannot be corrected.")

    new_value = utils.ensure_utc(new_value)
    old_value = record.get(field)

    # Validate chronological consistency after the proposed change.
    new_punch_in = new_value if field == "punch_in" else record.get("punch_in")
    new_punch_out = new_value if field == "punch_out" else record.get("punch_out")
    if (
        new_punch_in is not None
        and new_punch_out is not None
        and utils.ensure_utc(new_punch_out) < utils.ensure_utc(new_punch_in)
    ):
        raise InvalidCorrectionError(
            "Resulting punch-out time cannot be earlier than punch-in time."
        )

    update: dict = {field: new_value, "updated_at": utils.utcnow()}
    update["is_late"] = utils.is_late(new_punch_in)
    update["work_date"] = utils.work_date_str(new_punch_in)
    if new_punch_out is not None:
        minutes = utils.worked_minutes(new_punch_in, new_punch_out)
        update["worked_minutes"] = minutes
        update["is_overtime"] = minutes > settings.standard_work_minutes
        update["status"] = SessionStatus.CLOSED.value

    await coll.update_one({"_id": oid}, {"$set": update})

    audit_doc = {
        "attendance_id": attendance_id,
        "field": field,
        "old_value": utils.ensure_utc(old_value) if old_value else None,
        "new_value": new_value,
        "reason": reason,
        "corrected_by": corrected_by,
        "corrected_at": utils.utcnow(),
    }
    audit_result = await db[AUDIT_COLLECTION].insert_one(audit_doc)
    audit_doc["_id"] = audit_result.inserted_id

    record.update(update)
    return {
        "record": utils.serialize(record),
        "audit": utils.serialize(audit_doc),
    }


async def list_audit(db: AsyncIOMotorDatabase, attendance_id: str) -> list[dict]:
    cursor = (
        db[AUDIT_COLLECTION]
        .find({"attendance_id": attendance_id})
        .sort("corrected_at", -1)
    )
    return [utils.serialize(doc) async for doc in cursor]
