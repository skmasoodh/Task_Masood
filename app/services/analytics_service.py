"""Analytics built on MongoDB aggregation pipelines.

All reports only consider closed sessions (those with a punch-out and computed
``worked_minutes``) so that in-progress sessions do not skew totals.
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import ATTENDANCE_COLLECTION
from app.schemas.attendance import SessionStatus


def _date_match(
    employee_id: str | None,
    start_date: str | None,
    end_date: str | None,
) -> dict:
    match: dict = {"status": SessionStatus.CLOSED.value}
    if employee_id:
        match["employee_id"] = employee_id
    if start_date or end_date:
        date_range: dict = {}
        if start_date:
            date_range["$gte"] = start_date
        if end_date:
            date_range["$lte"] = end_date
        match["work_date"] = date_range
    return match


async def employee_summary(
    db: AsyncIOMotorDatabase,
    employee_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Per-employee totals: days present, worked minutes, late and overtime."""
    pipeline = [
        {"$match": _date_match(employee_id, start_date, end_date)},
        {
            "$group": {
                "_id": "$employee_id",
                "days_present": {"$sum": 1},
                "total_worked_minutes": {"$sum": "$worked_minutes"},
                "average_worked_minutes": {"$avg": "$worked_minutes"},
                "late_count": {"$sum": {"$cond": ["$is_late", 1, 0]}},
                "overtime_days": {"$sum": {"$cond": ["$is_overtime", 1, 0]}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "employee_id": "$_id",
                "days_present": 1,
                "total_worked_minutes": 1,
                "average_worked_minutes": {
                    "$round": [{"$ifNull": ["$average_worked_minutes", 0]}, 2]
                },
                "late_count": 1,
                "overtime_days": 1,
            }
        },
        {"$sort": {"employee_id": 1}},
    ]
    return [doc async for doc in db[ATTENDANCE_COLLECTION].aggregate(pipeline)]


async def daily_report(
    db: AsyncIOMotorDatabase,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Per-day headcount, total worked minutes and late arrivals."""
    pipeline = [
        {"$match": _date_match(None, start_date, end_date)},
        {
            "$group": {
                "_id": "$work_date",
                "employees_present": {"$addToSet": "$employee_id"},
                "total_worked_minutes": {"$sum": "$worked_minutes"},
                "late_count": {"$sum": {"$cond": ["$is_late", 1, 0]}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "work_date": "$_id",
                "employees_present": {"$size": "$employees_present"},
                "total_worked_minutes": 1,
                "late_count": 1,
            }
        },
        {"$sort": {"work_date": 1}},
    ]
    return [doc async for doc in db[ATTENDANCE_COLLECTION].aggregate(pipeline)]


async def late_arrivals(
    db: AsyncIOMotorDatabase,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Employees ranked by number of late punch-ins."""
    match = _date_match(None, start_date, end_date)
    match["is_late"] = True
    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$employee_id", "late_count": {"$sum": 1}}},
        {"$project": {"_id": 0, "employee_id": "$_id", "late_count": 1}},
        {"$sort": {"late_count": -1, "employee_id": 1}},
    ]
    return [doc async for doc in db[ATTENDANCE_COLLECTION].aggregate(pipeline)]
