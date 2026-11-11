"""Build the question set from active goals (FR-2.2)."""

from dataclasses import dataclass
from datetime import date

from myziel.modules.profile_goals.models import GoalVersion
from myziel.modules.profile_goals.targets import target_for_day

QUESTION_SET_VERSION = "v1"


@dataclass(frozen=True)
class GoalQuestion:
    key: str
    goal_version_id: int
    label: str
    metric: str
    unit: str
    target: float  # 0 means "not counted today"
    weight: float


def unit_label(unit: str) -> str:
    return {"count": "", "hours": "h", "minutes": "min", "done": ""}.get(unit, unit)


def goal_questions(goal_versions: list[GoalVersion], day: date) -> list[GoalQuestion]:
    out = []
    for v in goal_versions:
        if v.unit == "done":
            label = f"{v.title}: did you do it today?"
        else:
            label = f"{v.title}: how much {v.metric} today ({v.unit})?"
        out.append(
            GoalQuestion(
                key=f"goal_{v.goal_id}",
                goal_version_id=v.id,
                label=label,
                metric=v.metric,
                unit=v.unit,
                target=round(target_for_day(v.daily_target, day, v.weekdays_only), 4),
                weight=float(v.priority),
            )
        )
    return out


# Core questions asked every day, in addition to 1 per goal.
CORE_QUESTIONS = [
    ("energy", "Energy today (1 = drained, 5 = great)"),
    ("sleep_hours", "Hours slept last night"),
    ("mood", "Mood (1 = low, 5 = great)"),
    ("blocker", "Main blocker today (optional)"),
    ("raw_text", "Anything else about today? (free text)"),
    ("self_rating", "How would you rate today yourself?"),
]
