"""Pydantic request/response models (API contract)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


# ----- Requests -------------------------------------------------------------
class PunchRequest(BaseModel):
    employee_id: str = Field(..., min_length=1, examples=["EMP-001"])
    # Optional override, mainly useful for seeding/testing. Server time is used
    # when omitted.
    timestamp: datetime | None = None


class CorrectionField(str, Enum):
    PUNCH_IN = "punch_in"
    PUNCH_OUT = "punch_out"


class CorrectionRequest(BaseModel):
    field: CorrectionField
    new_value: datetime
    reason: str = Field(..., min_length=3, max_length=500)
    corrected_by: str = Field(..., min_length=1, examples=["admin@corp.com"])


# ----- Responses ------------------------------------------------------------
class AttendanceRecord(BaseModel):
    id: str
    employee_id: str
    work_date: str
    punch_in: datetime
    punch_out: datetime | None = None
    status: SessionStatus
    worked_minutes: int | None = None
    is_late: bool = False
    is_overtime: bool = False
    created_at: datetime
    updated_at: datetime


class AuditRecord(BaseModel):
    id: str
    attendance_id: str
    field: str
    old_value: datetime | None = None
    new_value: datetime
    reason: str
    corrected_by: str
    corrected_at: datetime


# ----- Analytics ------------------------------------------------------------
class EmployeeSummary(BaseModel):
    employee_id: str
    days_present: int
    total_worked_minutes: int
    average_worked_minutes: float
    late_count: int
    overtime_days: int


class DailyReport(BaseModel):
    work_date: str
    employees_present: int
    total_worked_minutes: int
    late_count: int


class LateArrival(BaseModel):
    employee_id: str
    late_count: int
