"""EWMA completion forecast with low/high range (FR-5.3). Pure functions."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class Forecast:
    pace_per_day: float
    projected: date | None
    optimistic: date | None
    pessimistic: date | None


def ewma(values: Sequence[float], span: int = 14) -> float:
    """Exponentially weighted mean, newest value last.

    Normalised weights (like pandas adjust=True), so short histories are not dominated by
    their oldest value.
    """
    if not values:
        return 0.0
    decay = 1 - 2 / (span + 1)
    weights = [decay ** (len(values) - 1 - i) for i in range(len(values))]
    return sum(w * v for w, v in zip(weights, values, strict=True)) / sum(weights)


def _finish(today: date, remaining: float, pace: float) -> date | None:
    if pace <= 0:
        return None
    return today + timedelta(days=math.ceil(remaining / pace))


def forecast_completion(
    daily_values: Sequence[float], remaining: float, today: date, window: int = 14
) -> Forecast:
    """Project when `remaining` is reached at the recent pace.

    The optimistic / pessimistic dates use pace +/- one standard deviation of the window.
    """
    recent = list(daily_values[-window:])
    if remaining <= 0:
        return Forecast(ewma(recent), today, today, today)
    pace = ewma(recent, span=window)
    if len(recent) > 1:
        mean = sum(recent) / len(recent)
        std = math.sqrt(sum((v - mean) ** 2 for v in recent) / (len(recent) - 1))
    else:
        std = 0.0
    return Forecast(
        pace_per_day=pace,
        projected=_finish(today, remaining, pace),
        optimistic=_finish(today, remaining, pace + std),
        pessimistic=_finish(today, remaining, pace - std),
    )


def days_behind(projected: date | None, deadline: date | None) -> int | None:
    """Positive = behind schedule by N days, 0 or negative = on track."""
    if projected is None or deadline is None:
        return None
    return (projected - deadline).days
