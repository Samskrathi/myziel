"""Drift detection (FR-3.1, FR-3.2). Pure functions."""

from collections.abc import Mapping, Sequence
from datetime import date, timedelta


def rolling_pace(values: Mapping[date, float], end: date, window: int = 7) -> float:
    """Average per day over the `window` days ending at `end` (missing days count as 0)."""
    total = sum(values.get(end - timedelta(days=i), 0.0) for i in range(window))
    return total / window


def required_pace(remaining: float, today: date, deadline: date) -> float:
    days_left = (deadline - today).days + 1
    if remaining <= 0:
        return 0.0
    if days_left <= 0:
        return float("inf")
    return remaining / days_left


def is_behind(pace: float, required: float, tolerance: float = 0.2) -> bool:
    return required > 0 and pace < required * (1 - tolerance)


def sustained(flags: Sequence[bool], min_days: int = 3) -> bool:
    """True when the last `min_days` flags (oldest first) are all set."""
    return len(flags) >= min_days and all(flags[-min_days:])


def consecutive_tail(items: Sequence[str], value: str) -> int:
    n = 0
    for item in reversed(items):
        if item != value:
            break
        n += 1
    return n


def extra_signals(lights: Sequence[str], blockers_this_week: Sequence[str]) -> list[str]:
    """FR-3.2. `lights` is oldest-first per day ('green', 'amber', 'red', 'grey')."""
    signals = []
    if consecutive_tail(lights, "red") >= 2:
        signals.append("2 red days in a row")
    if consecutive_tail(lights, "grey") >= 2:
        signals.append("2 missed check-ins in a row")
    counts: dict[str, int] = {}
    for b in blockers_this_week:
        key = b.strip().lower()
        if key:
            counts[key] = counts.get(key, 0) + 1
    signals += [f"blocker '{b}' mentioned {n} times" for b, n in counts.items() if n >= 3]
    return signals
