"""Calendar and dashboard queries (FR-4, FR-5.1 basic)."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from myziel.core.clock import parse_hhmm, to_local
from myziel.modules.analytics.calendar import DayCell, day_state, month_weeks
from myziel.modules.auth.models import User
from myziel.modules.auth.service import user_settings
from myziel.modules.checkin.models import CheckIn
from myziel.modules.checkin.service import is_missed, open_checkin_date
from myziel.modules.profile_goals.models import GoalVersion
from myziel.modules.profile_goals.service import active_goal_versions
from myziel.modules.profile_goals.targets import target_for_day
from myziel.modules.scoring.models import DayScore
from myziel.modules.scoring.streaks import checkin_streak, productivity_streak


@dataclass
class DayRecord:
    checkin: CheckIn
    score: DayScore | None


def records_between(session: Session, user: User, start: date, end: date) -> dict[date, DayRecord]:
    rows = session.execute(
        select(CheckIn, DayScore)
        .outerjoin(DayScore, DayScore.checkin_id == CheckIn.id)
        .where(CheckIn.user_id == user.id, CheckIn.local_date.between(start, end))
    ).all()
    return {c.local_date: DayRecord(c, s) for c, s in rows}


@dataclass
class TimeContext:
    local_now: datetime
    local_today: date
    open_day: date | None
    first_day: date
    window: tuple
    settings: dict = field(default_factory=dict)


def time_context(user: User, now_utc: datetime) -> TimeContext:
    s = user_settings(user)
    start, end = parse_hhmm(s["checkin_window_start"]), parse_hhmm(s["checkin_window_end"])
    local_now = to_local(now_utc, user.timezone)
    return TimeContext(
        local_now=local_now,
        local_today=local_now.date(),
        open_day=open_checkin_date(local_now, start, end),
        first_day=to_local(user.created_at, user.timezone).date(),
        window=(start, end),
        settings=s,
    )


def _light_for(rec: DayRecord | None, mode: str) -> str | None:
    if rec is None:
        return None
    if mode == "self":
        return rec.checkin.self_rating
    return rec.score.light if rec.score else "none"


def month_cells(
    session: Session, user: User, year: int, month: int, now_utc: datetime, mode: str = "score"
) -> list[list[DayCell]]:
    weeks = month_weeks(year, month)
    tc = time_context(user, now_utc)
    records = records_between(session, user, weeks[0][0], weeks[-1][-1])
    out = []
    for week in weeks:
        row = []
        for d in week:
            rec = records.get(d)
            state = day_state(
                d,
                light=_light_for(rec, mode),
                open_day=tc.open_day,
                local_today=tc.local_today,
                missed=is_missed(d, tc.local_now, *tc.window, submitted=rec is not None),
                first_day=tc.first_day,
            )
            score = rec.score.score if rec and rec.score else None
            row.append(DayCell(d, d.month == month, state, score))
        out.append(row)
    return out


@dataclass
class GoalBreakdown:
    version: GoalVersion
    value: float
    target: float


def day_detail(session: Session, user: User, day: date) -> tuple[DayRecord | None, list]:
    rec = records_between(session, user, day, day).get(day)
    if rec is None:
        return None, []
    breakdown = [
        GoalBreakdown(session.get(GoalVersion, v.goal_version_id), v.value, v.daily_target)
        for v in rec.checkin.values
    ]
    return rec, breakdown


@dataclass
class GoalWeek:
    title: str
    unit: str
    actual: float
    target: float

    @property
    def percent(self) -> int:
        return round(100 * self.actual / self.target) if self.target else 0


@dataclass
class Dashboard:
    days: list[date]
    scores: list[float | None]
    lights: list[str]
    goals: list[GoalWeek]
    checkin_streak: int
    productivity_streak: int
    open_day: date | None
    open_day_done: bool
    week_start: date


def dashboard(session: Session, user: User, now_utc: datetime) -> Dashboard:
    tc = time_context(user, now_utc)
    today = tc.local_today
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    history = records_between(session, user, today - timedelta(days=400), today)

    scores, lights = [], []
    for d in days:
        rec = history.get(d)
        scores.append(rec.score.score if rec and rec.score else None)
        if rec:
            lights.append(_light_for(rec, "score") or "none")
        elif d >= tc.first_day and is_missed(d, tc.local_now, *tc.window, submitted=False):
            lights.append("grey")
        else:
            lights.append("pending" if d == today else "future")

    # Goal progress Monday..today, summed per goal across its versions.
    week_start = today - timedelta(days=today.weekday())
    actual: dict[int, float] = defaultdict(float)
    for d, rec in history.items():
        if d >= week_start:
            for v in rec.checkin.values:
                gv = session.get(GoalVersion, v.goal_version_id)
                if gv is not None:
                    actual[gv.goal_id] += v.value
    goals = []
    for gv in active_goal_versions(session, user):
        target = sum(
            target_for_day(gv.daily_target, week_start + timedelta(days=i), gv.weekdays_only)
            for i in range(7)
        )
        goals.append(GoalWeek(gv.title, gv.unit, round(actual[gv.goal_id], 2), round(target, 2)))

    # Streaks end at the open day if it is done, otherwise at the last closed day.
    open_done = tc.open_day is not None and tc.open_day in history
    if tc.open_day is None:
        streak_end = today - timedelta(days=1)
    elif open_done:
        streak_end = tc.open_day
    else:
        streak_end = tc.open_day - timedelta(days=1)
    s = tc.settings
    return Dashboard(
        days=days,
        scores=scores,
        lights=lights,
        goals=goals,
        checkin_streak=checkin_streak(set(history), streak_end),
        productivity_streak=productivity_streak(
            {d: r.score.score if r.score else None for d, r in history.items()},
            streak_end,
            green_threshold=s["green_threshold"],
        ),
        open_day=tc.open_day,
        open_day_done=open_done,
        week_start=week_start,
    )
