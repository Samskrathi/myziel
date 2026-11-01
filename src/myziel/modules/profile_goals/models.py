"""profile_answer, goal, goal_version tables."""

from datetime import date, datetime

from sqlalchemy import (
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


class ProfileAnswer(Base):
    """Each change appends a new version (FR-1.4)."""

    __tablename__ = "profile_answer"
    __table_args__ = (UniqueConstraint("user_id", "question_key", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    question_key: Mapped[str] = mapped_column(String(64))
    answer: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Goal(Base):
    __tablename__ = "goal"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    versions: Mapped[list["GoalVersion"]] = relationship(
        back_populates="goal", order_by="GoalVersion.version", lazy="selectin"
    )

    @property
    def current(self) -> "GoalVersion":
        return self.versions[-1]


class GoalVersion(Base):
    """Immutable snapshot of a goal. Editing a goal inserts a new row."""

    __tablename__ = "goal_version"
    __table_args__ = (UniqueConstraint("goal_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    goal_id: Mapped[int] = mapped_column(ForeignKey("goal.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    why: Mapped[str] = mapped_column(Text, default="")
    goal_type: Mapped[str] = mapped_column(String(16))  # outcome | habit
    metric: Mapped[str] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(String(32))  # count | hours | minutes | done
    target_value: Mapped[float] = mapped_column(Float)
    target_period: Mapped[str] = mapped_column(String(8))  # day | week | total
    weekdays_only: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekly_budget_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=2)  # 1 low, 2 medium, 3 high
    status: Mapped[str] = mapped_column(String(16), default="active")
    daily_target: Mapped[float] = mapped_column(Float)
    daily_target_is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    goal: Mapped[Goal] = relationship(back_populates="versions")
