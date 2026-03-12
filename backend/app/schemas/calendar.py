"""Pydantic schemas for calendar API."""

import uuid
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, field_validator

from app.models.base import ScheduleType


# --- Schedule Config Schemas ---

class ScheduleConfigBase(BaseModel):
    timezone: str = "UTC"
    work_days: list[int] = [0, 1, 2, 3, 4]
    work_start_time: time = time(9, 0)
    work_end_time: time = time(17, 0)
    day_overrides: dict | None = None

    @field_validator("work_days")
    @classmethod
    def validate_work_days(cls, v: list[int]) -> list[int]:
        for day in v:
            if not 0 <= day <= 6:
                raise ValueError("Work days must be 0-6 (Monday=0, Sunday=6)")
        return v


class ScheduleConfigCreate(ScheduleConfigBase):
    pass


class ScheduleConfigUpdate(BaseModel):
    timezone: str | None = None
    work_days: list[int] | None = None
    work_start_time: time | None = None
    work_end_time: time | None = None
    day_overrides: dict | None = None


class ScheduleConfigResponse(ScheduleConfigBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Calendar Event Schemas ---

class CalendarEventBase(BaseModel):
    schedule_type: ScheduleType
    title: str
    description: str | None = None
    start_datetime: datetime
    end_datetime: datetime
    all_day: bool = False
    timezone: str = "UTC"
    rrule: str | None = None


class CalendarEventCreate(CalendarEventBase):
    pass


class CalendarEventUpdate(BaseModel):
    schedule_type: ScheduleType | None = None
    title: str | None = None
    description: str | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
    all_day: bool | None = None
    timezone: str | None = None
    rrule: str | None = None


class CalendarEventResponse(CalendarEventBase):
    id: uuid.UUID
    user_id: uuid.UUID
    is_recurring: bool
    recurrence_end: date | None
    exdates: list[str] | None
    parent_event_id: uuid.UUID | None
    external_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Availability Schemas ---

class TimeSlotResponse(BaseModel):
    start: time
    end: time


class DayAvailabilityResponse(BaseModel):
    date: date
    work_hours: TimeSlotResponse | None
    busy_slots: list[TimeSlotResponse]
    free_slots: list[TimeSlotResponse]


class AvailabilityGridResponse(BaseModel):
    days: list[DayAvailabilityResponse]
    summary: dict


class AvailabilitySummaryResponse(BaseModel):
    work_days: int
    total_work_hours: float
    total_busy_hours: float
    total_free_hours: float
    utilization_percent: float


# --- Query Parameters ---

class DateRangeQuery(BaseModel):
    start_date: date
    end_date: date


class SkipDateRequest(BaseModel):
    date: date
