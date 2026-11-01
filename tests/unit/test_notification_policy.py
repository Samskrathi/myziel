from datetime import date, time

from myziel.modules.notifications.policy import in_quiet_hours, should_send_checkin_reminder

TODAY = date(2026, 10, 5)


def params(**overrides):
    base = dict(
        enabled=True,
        local_time=time(20, 5),
        reminder_time=time(20, 0),
        open_day=TODAY,
        local_today=TODAY,
        already_checked_in=False,
        reminder_sent_today=False,
        sent_today_count=0,
        max_per_day=3,
        quiet_start=time(22, 30),
        quiet_end=time(7, 0),
    )
    base.update(overrides)
    return base


def test_quiet_hours_across_midnight():
    assert in_quiet_hours(time(23, 0), time(22, 30), time(7, 0))
    assert in_quiet_hours(time(6, 59), time(22, 30), time(7, 0))
    assert not in_quiet_hours(time(7, 0), time(22, 30), time(7, 0))


def test_quiet_hours_same_day_and_disabled():
    assert in_quiet_hours(time(13, 0), time(12, 0), time(14, 0))
    assert not in_quiet_hours(time(13, 0), time(0, 0), time(0, 0))


def test_sends_when_due():
    assert should_send_checkin_reminder(**params())


def test_not_before_reminder_time():
    assert not should_send_checkin_reminder(**params(local_time=time(19, 59)))


def test_not_twice_a_day():
    assert not should_send_checkin_reminder(**params(reminder_sent_today=True))


def test_not_when_already_checked_in():
    assert not should_send_checkin_reminder(**params(already_checked_in=True))


def test_daily_cap():
    assert not should_send_checkin_reminder(**params(sent_today_count=3))


def test_not_in_quiet_hours():
    assert not should_send_checkin_reminder(**params(local_time=time(23, 0)))


def test_not_when_disabled_or_window_closed():
    assert not should_send_checkin_reminder(**params(enabled=False))
    assert not should_send_checkin_reminder(**params(open_day=None))
