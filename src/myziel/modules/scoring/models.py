"""day_score table. (streak_event and pause_ledger arrive in phase 2.)"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from myziel.core.db import Base


class DayScore(Base):
    __tablename__ = "day_score"
    __table_args__ = (UniqueConstraint("user_id", "local_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    checkin_id: Mapped[int] = mapped_column(ForeignKey("checkin.id"))
    local_date: Mapped[date] = mapped_column(Date)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    light: Mapped[str] = mapped_column(String(8))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
