"""Quiet hours and anti-nagging limits (FR-6.3, FR-6.4). Pure functions."""

from datetime import date, time


def in_quiet_hours(t: time, start: time, end: time) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= t < end
    return t >= start or t < end  # spans midnight


def should_send_checkin_reminder(
    *,
    enabled: bool,
    local_time: time,
    reminder_time: time,
    open_day: date | None,
    local_today: date,
    already_checked_in: bool,
    reminder_sent_today: bool,
    sent_today_count: int,
    max_per_day: int,
    quiet_start: time,
    quiet_end: time,
) -> bool:
    return (
        enabled
        and open_day == local_today
        and local_time >= reminder_time
        and not already_checked_in
        and not reminder_sent_today
        and sent_today_count < max_per_day
        and not in_quiet_hours(local_time, quiet_start, quiet_end)
    )
