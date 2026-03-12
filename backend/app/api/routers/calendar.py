"""Calendar API endpoints for schedule config, events, and availability."""

import uuid
from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser
from app.db.session import DBSession
from app.schemas.calendar import (
    AvailabilityGridResponse,
    AvailabilitySummaryResponse,
    CalendarEventCreate,
    CalendarEventResponse,
    CalendarEventUpdate,
    DayAvailabilityResponse,
    ScheduleConfigCreate,
    ScheduleConfigResponse,
    ScheduleConfigUpdate,
    SkipDateRequest,
    TimeSlotResponse,
)
from app.services import availability_service, calendar_service
from app.services.rrule_helper import RRuleValidationError

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/config", response_model=ScheduleConfigResponse)
def get_config(db: DBSession, current_user: CurrentUser):
    """Get the current user's schedule configuration."""
    config = calendar_service.get_schedule_config(db, current_user.id)
    if not config:
        raise HTTPException(status_code=404, detail="Schedule config not found")
    return config


@router.post("/config", response_model=ScheduleConfigResponse, status_code=status.HTTP_201_CREATED)
def create_config(
    payload: ScheduleConfigCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create schedule configuration for the current user."""
    existing = calendar_service.get_schedule_config(db, current_user.id)
    if existing:
        raise HTTPException(status_code=400, detail="Schedule config already exists")

    config = calendar_service.create_schedule_config(
        db,
        current_user.id,
        timezone=payload.timezone,
        work_days=payload.work_days,
        work_start_time=payload.work_start_time,
        work_end_time=payload.work_end_time,
        day_overrides=payload.day_overrides,
    )
    return config


@router.put("/config", response_model=ScheduleConfigResponse)
def update_config(
    payload: ScheduleConfigUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update schedule configuration for the current user."""
    config = calendar_service.get_schedule_config(db, current_user.id)
    if not config:
        raise HTTPException(status_code=404, detail="Schedule config not found")

    update_data = payload.model_dump(exclude_unset=True)
    config = calendar_service.update_schedule_config(db, config, **update_data)
    return config


@router.post("/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: CalendarEventCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a new calendar event."""
    try:
        event = calendar_service.create_event(
            db,
            current_user.id,
            schedule_type=payload.schedule_type,
            title=payload.title,
            start_datetime=payload.start_datetime,
            end_datetime=payload.end_datetime,
            timezone=payload.timezone,
            description=payload.description,
            all_day=payload.all_day,
            rrule=payload.rrule,
        )
        return event
    except RRuleValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events", response_model=list[CalendarEventResponse])
def list_events(
    db: DBSession,
    current_user: CurrentUser,
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    """List calendar events within a date range."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    events = calendar_service.list_events(db, current_user.id, start_date, end_date)
    return events


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
def get_event(
    event_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Get a single calendar event."""
    event = calendar_service.get_event(db, event_id)
    if not event or event.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.put("/events/{event_id}", response_model=CalendarEventResponse)
def update_event(
    event_id: uuid.UUID,
    payload: CalendarEventUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update a calendar event."""
    event = calendar_service.get_event(db, event_id)
    if not event or event.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Event not found")

    try:
        update_data = payload.model_dump(exclude_unset=True)
        event = calendar_service.update_event(db, event, **update_data)
        return event
    except RRuleValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: uuid.UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete a calendar event."""
    event = calendar_service.get_event(db, event_id)
    if not event or event.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Event not found")

    calendar_service.delete_event(db, event)


@router.post("/events/{event_id}/skip/{skip_date}", response_model=CalendarEventResponse)
def skip_occurrence(
    event_id: uuid.UUID,
    skip_date: date,
    db: DBSession,
    current_user: CurrentUser,
):
    """Skip a specific occurrence of a recurring event."""
    event = calendar_service.get_event(db, event_id)
    if not event or event.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.is_recurring:
        raise HTTPException(status_code=400, detail="Event is not recurring")

    event = calendar_service.add_exception_date(db, event, skip_date)
    return event


@router.get("/availability", response_model=AvailabilityGridResponse)
def get_availability(
    db: DBSession,
    current_user: CurrentUser,
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    """Get free/busy availability grid for a date range."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    grid = availability_service.build_availability_grid(
        db, current_user.id, start_date, end_date
    )
    summary = availability_service.get_availability_summary(grid)

    days = []
    for day in grid:
        days.append(DayAvailabilityResponse(
            date=day.date,
            work_hours=TimeSlotResponse(start=day.work_hours.start, end=day.work_hours.end) if day.work_hours else None,
            busy_slots=[TimeSlotResponse(start=s.start, end=s.end) for s in day.busy_slots],
            free_slots=[TimeSlotResponse(start=s.start, end=s.end) for s in day.free_slots],
        ))

    return AvailabilityGridResponse(days=days, summary=summary)


@router.get("/availability/summary", response_model=AvailabilitySummaryResponse)
def get_availability_summary(
    db: DBSession,
    current_user: CurrentUser,
    start_date: date = Query(...),
    end_date: date = Query(...),
):
    """Get availability summary statistics for a date range."""
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be before end_date")

    grid = availability_service.build_availability_grid(
        db, current_user.id, start_date, end_date
    )
    summary = availability_service.get_availability_summary(grid)

    return AvailabilitySummaryResponse(**summary)
