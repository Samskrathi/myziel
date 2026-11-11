"""checkin, checkin_value, checkin_amendment tables. Append-only (see core/immutability.py)."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from myziel.core.db import Base


class CheckIn(Base):
    __tablename__ = "checkin"
    __table_args__ = (UniqueConstraint("user_id", "local_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    local_date: Mapped[date] = mapped_column(Date)
    submitted_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64))
    is_late: Mapped[bool] = mapped_column(Boolean)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    question_set_version: Mapped[str] = mapped_column(String(32))
    self_rating: Mapped[str] = mapped_column(String(8))  # green | amber | red
    energy: Mapped[int] = mapped_column(Integer)  # 1..5
    mood: Mapped[int] = mapped_column(Integer)  # 1..5
    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    blocker: Mapped[str] = mapped_column(Text, default="")
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hash: Mapped[str] = mapped_column(String(64))

    values: Mapped[list["CheckInValue"]] = relationship(lazy="selectin")
    amendments: Mapped[list["CheckInAmendment"]] = relationship(
        lazy="selectin", order_by="CheckInAmendment.created_at"
    )


class CheckInValue(Base):
    __tablename__ = "checkin_value"

    id: Mapped[int] = mapped_column(primary_key=True)
    checkin_id: Mapped[int] = mapped_column(ForeignKey("checkin.id"), index=True)
    goal_version_id: Mapped[int] = mapped_column(ForeignKey("goal_version.id"))
    metric: Mapped[str] = mapped_column(String(100))
    value: Mapped[float] = mapped_column(Float)
    # Snapshot of the target that applied that day, so later goal edits never change scores.
    daily_target: Mapped[float] = mapped_column(Float)
    weight: Mapped[float] = mapped_column(Float)


class CheckInAmendment(Base):
    __tablename__ = "checkin_amendment"

    id: Mapped[int] = mapped_column(primary_key=True)
    checkin_id: Mapped[int] = mapped_column(ForeignKey("checkin.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    note: Mapped[str] = mapped_column(Text)
    corrected_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
