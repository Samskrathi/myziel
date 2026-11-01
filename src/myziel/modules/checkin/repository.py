"""Insert-only access; no update or delete methods (FR-2.5)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from myziel.modules.checkin.models import CheckIn, CheckInAmendment


def add(session: Session, obj: CheckIn | CheckInAmendment) -> None:
    session.add(obj)


def get_by_date(session: Session, user_id: int, day: date) -> CheckIn | None:
    return session.scalar(
        select(CheckIn).where(CheckIn.user_id == user_id, CheckIn.local_date == day)
    )


def latest(session: Session, user_id: int) -> CheckIn | None:
    return session.scalar(
        select(CheckIn).where(CheckIn.user_id == user_id).order_by(CheckIn.id.desc()).limit(1)
    )


def dates_between(session: Session, user_id: int, start: date, end: date) -> set[date]:
    return set(
        session.scalars(
            select(CheckIn.local_date).where(
                CheckIn.user_id == user_id,
                CheckIn.local_date >= start,
                CheckIn.local_date <= end,
            )
        )
    )


def all_for_user(session: Session, user_id: int) -> list[CheckIn]:
    return list(
        session.scalars(select(CheckIn).where(CheckIn.user_id == user_id).order_by(CheckIn.id))
    )
