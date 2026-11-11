"""Check-in window, late flag, submit, amendments, hash chain (FR-2.1, 2.6, 2.7)."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from myziel.core.clock import ensure_utc, parse_hhmm, to_local
from myziel.core.events import CheckInSubmitted, EventBus
from myziel.modules.auth.models import User
from myziel.modules.auth.service import user_settings
from myziel.modules.checkin import repository
from myziel.modules.checkin.models import CheckIn, CheckInAmendment, CheckInValue
from myziel.modules.checkin.questions import QUESTION_SET_VERSION, GoalQuestion, goal_questions
from myziel.modules.checkin.schemas import CheckInAnswers
from myziel.modules.profile_goals.service import active_goal_versions


class CheckInError(ValueError):
    pass


# ---------- window rules (pure) ----------

def _overnight(start: time, end: time) -> bool:
    return end <= start


def open_checkin_date(local_now: datetime, start: time, end: time) -> date | None:
    """Which day can be checked in right now, or None if no window is open.

    Overnight window (18:00 -> 10:00): 18:00-23:59 is today, 00:00-09:59 is yesterday.
    Same-day window (06:00 -> 23:00): only that range of today.
    """
    t, today = local_now.time(), local_now.date()
    if _overnight(start, end):
        if t >= start:
            return today
        if t < end:
            return today - timedelta(days=1)
        return None
    return today if start <= t < end else None


def window_closes_at(day: date, start: time, end: time) -> datetime:
    """Local (naive) moment the check-in window for `day` closes."""
    close_day = day + timedelta(days=1) if _overnight(start, end) else day
    return datetime.combine(close_day, end)


def window_opens_at(day: date, start: time) -> datetime:
    return datetime.combine(day, start)


def is_late(day: date, local_now: datetime) -> bool:
    """Late = submitted after midnight, i.e. on the next calendar day."""
    return local_now.date() > day


def is_missed(day: date, local_now: datetime, start: time, end: time, submitted: bool) -> bool:
    return not submitted and local_now.replace(tzinfo=None) >= window_closes_at(day, start, end)


# ---------- hash chain (pure) ----------

def record_hash(prev_hash: str | None, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(((prev_hash or "") + body).encode()).hexdigest()


def checkin_payload(c: CheckIn, values: list[CheckInValue]) -> dict[str, Any]:
    return {
        "user_id": c.user_id,
        "local_date": c.local_date.isoformat(),
        "submitted_at_utc": ensure_utc(c.submitted_at_utc).replace(tzinfo=None).isoformat(),
        "timezone": c.timezone,
        "is_late": c.is_late,
        "raw_text": c.raw_text,
        "question_set_version": c.question_set_version,
        "self_rating": c.self_rating,
        "energy": c.energy,
        "mood": c.mood,
        "sleep_hours": c.sleep_hours,
        "blocker": c.blocker,
        "values": sorted(
            [[v.goal_version_id, v.metric, v.value, v.daily_target, v.weight] for v in values]
        ),
    }


def verify_chain(checkins: list[CheckIn]) -> bool:
    prev = None
    for c in checkins:
        if c.prev_hash != prev or record_hash(prev, checkin_payload(c, c.values)) != c.hash:
            return False
        prev = c.hash
    return True


# ---------- service ----------

@dataclass
class CheckInContext:
    day: date | None
    is_late: bool
    already_submitted: bool
    questions: list[GoalQuestion]
    opens_at: datetime | None


def checkin_context(session: Session, user: User, now_utc: datetime) -> CheckInContext:
    s = user_settings(user)
    start, end = parse_hhmm(s["checkin_window_start"]), parse_hhmm(s["checkin_window_end"])
    local_now = to_local(now_utc, user.timezone)
    day = open_checkin_date(local_now, start, end)
    if day is None:
        return CheckInContext(None, False, False, [], window_opens_at(local_now.date(), start))
    done = repository.get_by_date(session, user.id, day) is not None
    questions = goal_questions(active_goal_versions(session, user), day)
    return CheckInContext(day, is_late(day, local_now), done, questions, None)


def submit_checkin(
    session: Session, bus: EventBus, user: User, answers: CheckInAnswers, now_utc: datetime
) -> CheckIn:
    ctx = checkin_context(session, user, now_utc)
    if ctx.day is None:
        raise CheckInError("The check-in window is closed right now.")
    if ctx.already_submitted:
        raise CheckInError("You already checked in for this day.")

    values = []
    for q in ctx.questions:
        value = answers.goal_values.get(q.goal_version_id, 0.0)
        if q.unit == "done":
            value = 1.0 if value else 0.0
        values.append(
            CheckInValue(
                goal_version_id=q.goal_version_id,
                metric=q.metric,
                value=value,
                daily_target=q.target,
                weight=q.weight,
            )
        )
    prev = repository.latest(session, user.id)
    checkin = CheckIn(
        user_id=user.id,
        local_date=ctx.day,
        submitted_at_utc=now_utc,
        timezone=user.timezone,
        is_late=ctx.is_late,
        raw_text=answers.raw_text.strip(),
        question_set_version=QUESTION_SET_VERSION,
        self_rating=answers.self_rating,
        energy=answers.energy,
        mood=answers.mood,
        sleep_hours=answers.sleep_hours,
        blocker=answers.blocker.strip(),
        prev_hash=prev.hash if prev else None,
        values=values,
    )
    checkin.hash = record_hash(checkin.prev_hash, checkin_payload(checkin, values))
    repository.add(session, checkin)
    try:
        session.flush()
        bus.publish(CheckInSubmitted(checkin.id, user.id, checkin.local_date), session)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CheckInError("You already checked in for this day.") from exc
    return checkin


def add_amendment(
    session: Session,
    checkin: CheckIn,
    note: str,
    now_utc: datetime,
    corrected_values: dict[str, Any] | None = None,
) -> CheckInAmendment:
    note = note.strip()
    if not note:
        raise CheckInError("An amendment needs a note.")
    amendment = CheckInAmendment(
        checkin_id=checkin.id,
        created_at=now_utc,
        note=note,
        corrected_values=corrected_values or {},
    )
    repository.add(session, amendment)
    session.commit()
    return amendment
