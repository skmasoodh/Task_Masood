"""Attendance endpoints: punch-in, punch-out, lookup and corrections."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database import get_database
from app.exceptions import (
    AlreadyPunchedInError,
    InvalidCorrectionError,
    NotPunchedInError,
    RecordNotFoundError,
)
from app.schemas.attendance import (
    AttendanceRecord,
    AuditRecord,
    CorrectionRequest,
    PunchRequest,
)
from app.services import attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/punch-in", response_model=AttendanceRecord, status_code=status.HTTP_201_CREATED)
async def punch_in(
    payload: PunchRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    try:
        return await attendance_service.punch_in(
            db, payload.employee_id, payload.timestamp
        )
    except AlreadyPunchedInError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/punch-out", response_model=AttendanceRecord)
async def punch_out(
    payload: PunchRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    try:
        return await attendance_service.punch_out(
            db, payload.employee_id, payload.timestamp
        )
    except NotPunchedInError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except InvalidCorrectionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/records", response_model=list[AttendanceRecord])
async def list_records(
    employee_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await attendance_service.list_records(db, employee_id, limit)


@router.get("/records/{attendance_id}", response_model=AttendanceRecord)
async def get_record(
    attendance_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    try:
        return await attendance_service.get_record(db, attendance_id)
    except RecordNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.patch("/records/{attendance_id}/correct")
async def correct_record(
    attendance_id: str,
    payload: CorrectionRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    try:
        return await attendance_service.apply_correction(
            db,
            attendance_id,
            payload.field.value,
            payload.new_value,
            payload.reason,
            payload.corrected_by,
        )
    except RecordNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except InvalidCorrectionError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/records/{attendance_id}/audit", response_model=list[AuditRecord])
async def list_audit(
    attendance_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await attendance_service.list_audit(db, attendance_id)
