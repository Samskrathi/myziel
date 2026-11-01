"""Check-in and productivity streaks with freeze days (FR-2.10). Pure functions."""

from collections.abc import Callable, Mapping
from datetime import date, timedelta


def current_streak(
    qualifies: Callable[[date], bool],
    end: date,
    *,
    freeze_every_days: int = 7,
    max_lookback_days: int = 3650,
) -> int:
    """Count consecutive qualifying days ending at `end`, walking backwards.

    One non-qualifying day can be "frozen" per `freeze_every_days` days, so it does not
    break the streak (but does not count towards its length). Set freeze_every_days=0 to
    disable freezes.
    """
    length = 0
    last_freeze: date | None = None
    day = end
    for _ in range(max_lookback_days):
        if qualifies(day):
            length += 1
        elif (
            freeze_every_days > 0
            and length > 0
            and (last_freeze is None or (last_freeze - day).days >= freeze_every_days)
            and qualifies(day - timedelta(days=1))
        ):
            last_freeze = day
        else:
            break
        day -= timedelta(days=1)
    return length


def checkin_streak(submitted: set[date], end: date, freeze_every_days: int = 7) -> int:
    return current_streak(lambda d: d in submitted, end, freeze_every_days=freeze_every_days)


def productivity_streak(
    scores: Mapping[date, float | None],
    end: date,
    green_threshold: float = 80,
    freeze_every_days: int = 7,
) -> int:
    def ok(d: date) -> bool:
        s = scores.get(d)
        return s is not None and s >= green_threshold

    return current_streak(ok, end, freeze_every_days=freeze_every_days)
