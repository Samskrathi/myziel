"""Day score and traffic light (FR-2.9)."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

Light = Literal["green", "amber", "red", "grey", "none"]

PROGRESS_CAP = 1.2


@dataclass(frozen=True)
class GoalProgress:
    actual: float
    target: float
    weight: float = 1.0


def goal_progress(actual: float, target: float) -> float:
    """min(actual / target, 1.2). Callers skip goals whose target is 0 that day."""
    if target <= 0:
        raise ValueError("target must be positive")
    return min(max(actual, 0.0) / target, PROGRESS_CAP)


def day_score(items: Iterable[GoalProgress]) -> float | None:
    """Weighted average progress across goals that count today, scaled to 0..100.

    Returns None when no goal has a target today (e.g. weekend for weekday-only goals).
    """
    counted = [i for i in items if i.target > 0 and i.weight > 0]
    if not counted:
        return None
    total_weight = sum(i.weight for i in counted)
    avg = sum(goal_progress(i.actual, i.target) * i.weight for i in counted) / total_weight
    return round(min(avg, 1.0) * 100, 1)


def traffic_light(score: float | None, green: float = 80, amber: float = 50) -> Light:
    if score is None:
        return "none"
    if score >= green:
        return "green"
    if score >= amber:
        return "amber"
    return "red"
