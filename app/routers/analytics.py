"""Analytics endpoints backed by MongoDB aggregation pipelines."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.schemas.attendance import DailyReport, EmployeeSummary, LateArrival
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/employee-summary", response_model=list[EmployeeSummary])
async def employee_summary(
    employee_id: str | None = Query(default=None),
    start_date: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    end_date: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await analytics_service.employee_summary(
        db, employee_id, start_date, end_date
    )


@router.get("/daily-report", response_model=list[DailyReport])
async def daily_report(
    start_date: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    end_date: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await analytics_service.daily_report(db, start_date, end_date)


@router.get("/late-arrivals", response_model=list[LateArrival])
async def late_arrivals(
    start_date: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    end_date: str | None = Query(default=None, description="YYYY-MM-DD inclusive"),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await analytics_service.late_arrivals(db, start_date, end_date)
