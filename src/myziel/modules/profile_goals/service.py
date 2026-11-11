"""Goal CRUD that always creates a new version (FR-1.4), active-goal limit (FR-1.5)."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from myziel.core.clock import to_local
from myziel.modules.auth.models import User
from myziel.modules.auth.service import user_settings
from myziel.modules.profile_goals.models import Goal, GoalVersion, ProfileAnswer
from myziel.modules.profile_goals.schemas import PROFILE_QUESTIONS, GoalInput
from myziel.modules.profile_goals.targets import derive_daily_target

HARD_MAX_ACTIVE_GOALS = 5


class GoalLimitReached(ValueError):
    pass


# ---------- profile ----------

def current_profile(session: Session, user: User) -> dict[str, str]:
    latest = (
        select(ProfileAnswer.question_key, func.max(ProfileAnswer.version).label("v"))
        .where(ProfileAnswer.user_id == user.id)
        .group_by(ProfileAnswer.question_key)
        .subquery()
    )
    rows = session.scalars(
        select(ProfileAnswer).join(
            latest,
            (ProfileAnswer.question_key == latest.c.question_key)
            & (ProfileAnswer.version == latest.c.v),
        ).where(ProfileAnswer.user_id == user.id)
    )
    return {r.question_key: r.answer for r in rows}


def save_profile(session: Session, user: User, answers: dict[str, str], now: datetime) -> int:
    """Append a new version for each changed answer. Returns how many changed."""
    allowed = {k for k, _ in PROFILE_QUESTIONS}
    current = current_profile(session, user)
    versions = dict(
        session.execute(
            select(ProfileAnswer.question_key, func.max(ProfileAnswer.version))
            .where(ProfileAnswer.user_id == user.id)
            .group_by(ProfileAnswer.question_key)
        ).all()
    )
    changed = 0
    for key, answer in answers.items():
        answer = answer.strip()
        if key not in allowed or current.get(key, "") == answer:
            continue
        session.add(
            ProfileAnswer(
                user_id=user.id,
                question_key=key,
                answer=answer,
                version=versions.get(key, 0) + 1,
                created_at=now,
            )
        )
        changed += 1
    session.commit()
    return changed


# ---------- goals ----------

def list_goals(session: Session, user: User) -> list[Goal]:
    return list(session.scalars(select(Goal).where(Goal.user_id == user.id).order_by(Goal.id)))


def get_goal(session: Session, user: User, goal_id: int) -> Goal | None:
    goal = session.get(Goal, goal_id)
    return goal if goal and goal.user_id == user.id else None


def active_goal_versions(session: Session, user: User) -> list[GoalVersion]:
    return [g.current for g in list_goals(session, user) if g.current.status == "active"]


def _max_active(user: User) -> int:
    return min(int(user_settings(user)["max_active_goals"]), HARD_MAX_ACTIVE_GOALS)


def _build_version(
    data: GoalInput, user: User, goal: Goal, version: int, now: datetime
) -> GoalVersion:
    start = to_local(now, user.timezone).date()
    if data.daily_target_override is not None:
        daily, custom = data.daily_target_override, True
    else:
        daily = derive_daily_target(
            data.target_value,
            data.target_period,
            weekdays_only=data.weekdays_only,
            start=start,
            deadline=data.deadline,
        )
        custom = False
    return GoalVersion(
        goal=goal,
        version=version,
        title=data.title.strip(),
        why=data.why.strip(),
        goal_type=data.goal_type,
        metric=data.metric.strip(),
        unit=data.unit,
        target_value=data.target_value,
        target_period=data.target_period,
        weekdays_only=data.weekdays_only,
        deadline=data.deadline,
        weekly_budget_hours=data.weekly_budget_hours,
        priority=data.priority,
        status=data.status,
        daily_target=round(daily, 4),
        daily_target_is_custom=custom,
        valid_from=now,
    )


def create_goal(session: Session, user: User, data: GoalInput, now: datetime) -> Goal:
    if data.status == "active" and len(active_goal_versions(session, user)) >= _max_active(user):
        raise GoalLimitReached(
            f"You already have {_max_active(user)} active goals. Pause or finish one first."
        )
    goal = Goal(user_id=user.id, created_at=now)
    session.add(goal)
    session.add(_build_version(data, user, goal, 1, now))
    session.commit()
    session.refresh(goal)
    return goal


def update_goal(session: Session, user: User, goal: Goal, data: GoalInput, now: datetime) -> Goal:
    """Never edits in place: appends version N+1. Old check-ins keep their version."""
    becoming_active = data.status == "active" and goal.current.status != "active"
    if becoming_active and len(active_goal_versions(session, user)) >= _max_active(user):
        raise GoalLimitReached(f"You already have {_max_active(user)} active goals.")
    session.add(_build_version(data, user, goal, goal.current.version + 1, now))
    session.commit()
    session.refresh(goal)
    return goal


def goal_to_input(v: GoalVersion) -> GoalInput:
    return GoalInput(
        title=v.title,
        why=v.why,
        goal_type=v.goal_type,  # type: ignore[arg-type]
        metric=v.metric,
        unit=v.unit,  # type: ignore[arg-type]
        target_value=v.target_value,
        target_period=v.target_period,  # type: ignore[arg-type]
        weekdays_only=v.weekdays_only,
        deadline=v.deadline,
        weekly_budget_hours=v.weekly_budget_hours,
        priority=v.priority,
        status=v.status,  # type: ignore[arg-type]
        daily_target_override=v.daily_target if v.daily_target_is_custom else None,
    )
