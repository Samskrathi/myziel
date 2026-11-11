"""User creation, login, settings, data export and account deletion (NFR-5, NFR-6)."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from myziel.core.db import get_db
from myziel.core.security import hash_password, verify_password
from myziel.modules.auth.models import AccountDeletion, User
from myziel.modules.checkin.models import CheckIn, CheckInAmendment, CheckInValue
from myziel.modules.notifications.models import Notification
from myziel.modules.profile_goals.models import Goal, GoalVersion, ProfileAnswer
from myziel.modules.scoring.models import DayScore

DEFAULT_SETTINGS: dict[str, Any] = {
    "checkin_window_start": "18:00",
    "checkin_window_end": "10:00",
    "reminder_enabled": True,
    "reminder_time": "20:00",
    "quiet_hours_start": "22:30",
    "quiet_hours_end": "07:00",
    "max_notifications_per_day": 3,
    "green_threshold": 80,
    "amber_threshold": 50,
    "max_active_goals": 3,
    "calendar_mode": "score",  # score | self
}


class LoginRequired(Exception):
    pass


def validate_timezone(tz: str) -> str:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown timezone: {tz}") from exc
    return tz


def user_settings(user: User) -> dict[str, Any]:
    return {**DEFAULT_SETTINGS, **(user.settings or {})}


def user_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(User)) or 0


def create_user(session: Session, email: str, password: str, tz: str, now: datetime) -> User:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    user = User(
        email=email.strip().lower(),
        password_hash=hash_password(password),
        timezone=validate_timezone(tz),
        settings={},
        created_at=now,
    )
    session.add(user)
    session.commit()
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user and verify_password(password, user.password_hash):
        return user
    return None


def update_settings(session: Session, user: User, changes: dict[str, Any]) -> None:
    unknown = set(changes) - set(DEFAULT_SETTINGS)
    if unknown:
        raise ValueError(f"Unknown settings: {sorted(unknown)}")
    user.settings = {**(user.settings or {}), **changes}  # reassign so JSON change is tracked
    session.commit()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise LoginRequired()
    return user


def export_user_data(session: Session, user: User) -> dict[str, Any]:
    def plain(value: Any) -> Any:
        return value.isoformat() if hasattr(value, "isoformat") else value

    def rows(model: Any, *where: Any) -> list[dict[str, Any]]:
        return [
            {c.name: plain(getattr(obj, c.key)) for c in model.__table__.columns}
            for obj in session.scalars(select(model).where(*where))
        ]

    goal_ids = select(Goal.id).where(Goal.user_id == user.id)
    checkin_ids = select(CheckIn.id).where(CheckIn.user_id == user.id)
    profile = {"id": user.id, "email": user.email, "timezone": user.timezone,
               "settings": user_settings(user), "created_at": user.created_at.isoformat()}
    return {
        "user": profile,
        "profile_answers": rows(ProfileAnswer, ProfileAnswer.user_id == user.id),
        "goals": rows(Goal, Goal.user_id == user.id),
        "goal_versions": rows(GoalVersion, GoalVersion.goal_id.in_(goal_ids)),
        "checkins": rows(CheckIn, CheckIn.user_id == user.id),
        "checkin_values": rows(CheckInValue, CheckInValue.checkin_id.in_(checkin_ids)),
        "checkin_amendments": rows(
            CheckInAmendment, CheckInAmendment.checkin_id.in_(checkin_ids)
        ),
        "day_scores": rows(DayScore, DayScore.user_id == user.id),
        "notifications": rows(Notification, Notification.user_id == user.id),
    }


def delete_account(session: Session, user: User, now: datetime) -> None:
    """The only path allowed to remove check-ins (NFR-6)."""
    uid = user.id
    session.add(AccountDeletion(user_id=uid, created_at=now))
    session.flush()
    checkin_ids = select(CheckIn.id).where(CheckIn.user_id == uid)
    goal_ids = select(Goal.id).where(Goal.user_id == uid)
    session.execute(delete(Notification).where(Notification.user_id == uid))
    session.execute(delete(DayScore).where(DayScore.user_id == uid))
    session.execute(delete(CheckInValue).where(CheckInValue.checkin_id.in_(checkin_ids)))
    session.execute(
        delete(CheckInAmendment).where(CheckInAmendment.checkin_id.in_(checkin_ids))
    )
    session.execute(delete(CheckIn).where(CheckIn.user_id == uid))
    session.execute(delete(GoalVersion).where(GoalVersion.goal_id.in_(goal_ids)))
    session.execute(delete(Goal).where(Goal.user_id == uid))
    session.execute(delete(ProfileAnswer).where(ProfileAnswer.user_id == uid))
    session.execute(delete(User).where(User.id == uid))
    session.commit()
