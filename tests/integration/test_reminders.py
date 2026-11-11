"""Email check-in reminder job (FR-6, Phase 1)."""

from myziel.modules.notifications.scheduler import run_reminders
from tests.conftest import EMAIL, add_goal, checkin_form, utc


def run(app):
    return run_reminders(app.state.sessionmaker, app.state.clock, app.state.channel)


def test_reminder_sent_once_when_due(user_client, app, channel, clock):
    clock.set(utc(2026, 10, 5, 18, 5))  # 20:05 Berlin, reminder time 20:00
    assert run(app) == 1
    assert channel.sent[0][0] == EMAIL
    assert run(app) == 0  # not twice the same day


def test_no_reminder_before_time(user_client, app, clock):
    clock.set(utc(2026, 10, 5, 17, 30))  # 19:30 Berlin
    assert run(app) == 0


def test_no_reminder_after_checkin(user_client, app, clock):
    add_goal(user_client)
    user_client.post("/checkin/submit", data={**checkin_form(goal_1="1"), "action": "submit"})
    assert run(app) == 0


def test_no_reminder_in_quiet_hours(user_client, app, clock):
    clock.set(utc(2026, 10, 5, 21, 0))  # 23:00 Berlin
    assert run(app) == 0


def test_failed_send_is_recorded_and_retried(user_client, app, channel, clock):
    def boom(*_args):
        raise OSError("smtp down")

    channel.send = boom
    clock.set(utc(2026, 10, 5, 18, 5))
    assert run(app) == 0
    del channel.send  # restore the class method
    assert run(app) == 1
