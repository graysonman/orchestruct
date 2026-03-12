import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum as SQLEnum, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ScopeType(str, enum.Enum):
    USER = "user"
    TEAM = "team"
    ORG = "org"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ScopedMixin:
    scope_type: Mapped[ScopeType] = mapped_column(
        SQLEnum(ScopeType),
        nullable=False
    )
    scope_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False
    )


class ScheduleType(str, enum.Enum):
    WORK = "work"
    PERSONAL = "personal"
    BLOCKED = "blocked"
    
