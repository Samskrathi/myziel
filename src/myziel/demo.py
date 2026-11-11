"""Public demo mode (DEMO_MODE=true).

On startup an empty database gets one demo account with a profile, three goals and about
two months of check-ins, so a visitor lands on a filled calendar and dashboard. Visitors
enter through /demo without a password. Account deletion and setup are disabled.

Check-ins go through the normal service (window rules, hash chain, scoring events), only
with the clock set to each past evening, so the seeded data is exactly what real use
would produce.
"""

import random
import secrets
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from myziel.core.events import EventBus
from myziel.core.logging import get_logger
from myziel.modules.auth.models import User
from myziel.modules.auth.service import create_user, update_settings, user_count
from myziel.modules.checkin.schemas import CheckInAnswers
from myziel.modules.checkin.service import checkin_context, submit_checkin
from myziel.modules.profile_goals.schemas import GoalInput
from myziel.modules.profile_goals.service import create_goal, save_profile

log = get_logger(__name__)

DEMO_EMAIL = "demo@myziel.app"
DEMO_TZ = "Europe/Berlin"
DEMO_DAYS = 60

# Paths a demo visitor may not POST to: they would lock others out or wipe the demo.
BLOCKED_POSTS = ("/setup", "/login", "/account/delete")

BLOCKERS = ["", "", "", "Late meeting ran over", "Slept badly", "Too many small tasks",
            "Got distracted by email", "", "Travel day", ""]
NOTES = ["Good focus in the morning.", "Felt slow after lunch.", "", "Solid day overall.",
         "Hard to start, better in the evening.", "", "Short on time but kept the streak."]


def _goals(today: date) -> list[GoalInput]:
    return [
        GoalInput(title="Reach German B1", why="Feel at home in Germany", goal_type="habit",
                  metric="study time", unit="minutes", target_value=45, target_period="day",
                  priority=3),
        GoalInput(title="Ship my side project", why="Have something real to show",
                  goal_type="outcome", metric="build time", unit="hours", target_value=60,
                  target_period="total", weekdays_only=True,
                  deadline=today + timedelta(days=30), priority=2),
        GoalInput(title="Run regularly", why="More energy, better sleep", goal_type="habit",
                  metric="run", unit="done", target_value=1, target_period="day", priority=1),
    ]


PROFILE = {
    "situation": "Backend engineer, learning German and building a side project",
    "working_hours": "09:00 to 17:30 on weekdays",
    "energy_peaks": "Early morning and after 20:00",
    "commitments": "German class Tuesday and Thursday evening",
    "derailers": "Long meetings and scrolling my phone at night",
}


def _local_evening(day: date, tz: str) -> datetime:
    return datetime.combine(day, time(20, 30), ZoneInfo(tz)).astimezone(ZoneInfo("UTC"))


def seed_demo(make_session: sessionmaker[Session], bus: EventBus, now_utc: datetime) -> bool:
    """Fill an empty database with the demo account. Returns False if users already exist."""
    rng = random.Random(42)
    with make_session() as session:
        if user_count(session) > 0:
            return False
        today = now_utc.astimezone(ZoneInfo(DEMO_TZ)).date()
        start = today - timedelta(days=DEMO_DAYS)
        start_utc = _local_evening(start, DEMO_TZ) - timedelta(hours=2)

        user = create_user(session, DEMO_EMAIL, secrets.token_urlsafe(24), DEMO_TZ, start_utc)
        # Wide check-in window so visitors can try today's check-in at any hour.
        update_settings(session, user, {"checkin_window_start": "00:00",
                                        "checkin_window_end": "23:59",
                                        "reminder_enabled": False})
        save_profile(session, user, PROFILE, start_utc)
        for g in _goals(today):
            create_goal(session, user, g, start_utc)

        for offset in range(DEMO_DAYS, 0, -1):
            day = today - timedelta(days=offset)
            if rng.random() < 0.07:  # a few missed days show up grey
                continue
            at = _local_evening(day, DEMO_TZ)
            ctx = checkin_context(session, user, at)
            # Form improves over time: early weeks are patchier than recent ones.
            form = 0.55 + 0.4 * (1 - offset / DEMO_DAYS) + rng.uniform(-0.3, 0.25)
            values: dict[int, float] = {}
            for q in ctx.questions:
                if q.target == 0:
                    continue
                if q.unit == "done":
                    values[q.goal_version_id] = 1.0 if rng.random() < form else 0.0
                else:
                    raw = q.target * max(0.0, form + rng.uniform(-0.2, 0.2))
                    values[q.goal_version_id] = round(raw, 1 if q.unit == "hours" else 0)
            rating = "green" if form > 0.8 else "amber" if form > 0.55 else "red"
            answers = CheckInAnswers(
                energy=max(1, min(5, round(form * 5 + rng.uniform(-1, 1)))),
                mood=max(1, min(5, round(form * 5 + rng.uniform(-1, 1)))),
                sleep_hours=round(rng.uniform(5.5, 8.5) * 2) / 2,
                blocker=rng.choice(BLOCKERS) if rating != "green" else "",
                raw_text=rng.choice(NOTES),
                self_rating=rating,
                goal_values=values,
            )
            submit_checkin(session, bus, user, answers, at)
    log.info("demo.seeded", days=DEMO_DAYS)
    return True


def demo_user_id(session: Session) -> int | None:
    return session.scalar(select(User.id).where(User.email == DEMO_EMAIL))
