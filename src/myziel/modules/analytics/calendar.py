"""Month grid and per-day state for the traffic-light calendar (FR-4). Pure functions."""

import calendar
from dataclasses import dataclass
from datetime import date

ICONS = {
    "green": "●",
    "amber": "▲",
    "red": "■",
    "grey": "✕",
    "none": "○",
    "pending": "…",
    "future": "",
    "before": "",
}
LABELS = {
    "green": "On track",
    "amber": "Partly",
    "red": "Off track",
    "grey": "Missed",
    "none": "No targets",
    "pending": "Open",
    "future": "",
    "before": "",
}


@dataclass(frozen=True)
class DayCell:
    day: date
    in_month: bool
    state: str
    score: float | None = None

    @property
    def icon(self) -> str:
        return ICONS[self.state]

    @property
    def label(self) -> str:
        return LABELS[self.state]


def month_weeks(year: int, month: int) -> list[list[date]]:
    """Monday-first weeks covering the month, padded with neighbouring days."""
    return calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)


def day_state(
    day: date,
    *,
    light: str | None,
    open_day: date | None,
    local_today: date,
    missed: bool,
    first_day: date,
) -> str:
    """light: stored light for a submitted check-in (or self rating), None if no check-in."""
    if day < first_day:
        return "before"
    if light is not None:
        return light
    if missed:
        return "grey"
    if day == open_day or day == local_today:
        return "pending"
    return "future"


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    idx = year * 12 + (month - 1) + delta
    return idx // 12, idx % 12 + 1
