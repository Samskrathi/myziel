"""UTC clock and user-timezone helpers (FR-2.1, FR-6.5)."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from fastapi import Request


class Clock:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)


class FixedClock(Clock):
    """Clock for tests; time only moves when told to."""

    def __init__(self, now: datetime):
        self.now = now

    def now_utc(self) -> datetime:
        return self.now

    def set(self, now: datetime) -> None:
        self.now = now


def ensure_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo; values we store are always UTC."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def to_local(dt_utc: datetime, tz: str) -> datetime:
    return ensure_utc(dt_utc).astimezone(ZoneInfo(tz))


def local_today(now_utc: datetime, tz: str) -> date:
    return to_local(now_utc, tz).date()


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def get_clock(request: Request) -> Clock:
    return request.app.state.clock
