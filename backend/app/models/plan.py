import uuid
from datetime import date, datetime, time

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, ScopedMixin, TimestampMixin


class Plan(Base, TimestampMixin, ScopedMixin):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    planning_window_start: Mapped[date]
    planning_window_end: Mapped[date]
    status: Mapped[str] = mapped_column(String(50), default="draft")
    risk_summary: Mapped[dict | None] = mapped_column(JSON)
    items: Mapped[list["PlanItem"]] = relationship("PlanItem", back_populates="plan", lazy="select")


class PlanItem(Base):
    __tablename__ = "plan_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    start_time: Mapped[time]
    end_time: Mapped[time]
    scheduled_date: Mapped[date]
    risk_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rationale: Mapped[dict | None] = mapped_column(JSON)
    assigned_to_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    plan: Mapped["Plan"] = relationship("Plan", back_populates="items")