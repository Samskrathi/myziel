"""Reacts to CheckInSubmitted: stores the day score and traffic light."""

from sqlalchemy.orm import Session

from myziel.core.events import CheckInSubmitted, EventBus
from myziel.modules.auth.models import User
from myziel.modules.auth.service import user_settings
from myziel.modules.checkin.models import CheckIn
from myziel.modules.scoring.day_score import GoalProgress, day_score, traffic_light
from myziel.modules.scoring.models import DayScore


def on_checkin_submitted(event: CheckInSubmitted, session: Session) -> None:
    checkin = session.get(CheckIn, event.checkin_id)
    user = session.get(User, event.user_id)
    assert checkin is not None and user is not None
    s = user_settings(user)
    score = day_score(GoalProgress(v.value, v.daily_target, v.weight) for v in checkin.values)
    session.add(
        DayScore(
            user_id=user.id,
            checkin_id=checkin.id,
            local_date=checkin.local_date,
            score=score,
            light=traffic_light(score, s["green_threshold"], s["amber_threshold"]),
            computed_at=checkin.submitted_at_utc,
        )
    )


def register(bus: EventBus) -> None:
    bus.subscribe(CheckInSubmitted, on_checkin_submitted)
