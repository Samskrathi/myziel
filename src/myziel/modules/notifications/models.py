"""notification table. Preferences live in user.settings for v1."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from myziel.core.db import Base


class Notification(Base):
    __tablename__ = "notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    channel: Mapped[str] = mapped_column(String(16))
    local_date: Mapped[date] = mapped_column(Date)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))  # sent | failed
    detail: Mapped[str] = mapped_column(Text, default="")
