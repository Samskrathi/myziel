"""Derive daily/weekly targets from a goal (FR-1.3). Pure functions."""

from datetime import date, timedelta
from typing import Literal

Period = Literal["day", "week", "total"]


def is_active_day(day: date, weekdays_only: bool) -> bool:
    return not (weekdays_only and day.weekday() >= 5)


def count_active_days(start: date, end: date, weekdays_only: bool) -> int:
    """Active days in [start, end], both inclusive."""
    if end < start:
        return 0
    days = (end - start).days + 1
    if not weekdays_only:
        return days
    return sum(1 for i in range(days) if is_active_day(start + timedelta(days=i), True))


def derive_daily_target(
    target_value: float,
    period: Period,
    *,
    weekdays_only: bool = False,
    start: date | None = None,
    deadline: date | None = None,
) -> float:
    """Per-active-day target.

    day:   the value itself
    week:  spread over 5 weekdays or 7 days (5 per week, weekdays only -> 1 per weekday)
    total: spread over the active days from start to deadline
    """
    if target_value < 0:
        raise ValueError("target must not be negative")
    if period == "day":
        return target_value
    if period == "week":
        return target_value / (5 if weekdays_only else 7)
    if period == "total":
        if start is None or deadline is None:
            raise ValueError("a total target needs a start and a deadline")
        days = count_active_days(start, deadline, weekdays_only)
        if days <= 0:
            raise ValueError("deadline must be on or after the start date")
        return target_value / days
    raise ValueError(f"unknown period {period!r}")


def target_for_day(daily_target: float, day: date, weekdays_only: bool) -> float:
    """Target for a specific date; 0 means the goal does not count that day."""
    return daily_target if is_active_day(day, weekdays_only) else 0.0
