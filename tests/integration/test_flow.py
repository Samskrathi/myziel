"""End-to-end MVP flow through the web pages, with a fixed clock."""

import json

from sqlalchemy import select

from myziel.modules.checkin.models import CheckIn
from myziel.modules.profile_goals.models import GoalVersion
from myziel.modules.scoring.models import DayScore
from tests.conftest import EMAIL, add_goal, checkin_form, utc


def submit(client, **values):
    return client.post("/checkin/submit", data={**checkin_form(**values), "action": "submit"})


def test_first_visit_leads_to_setup(client):
    r = client.get("/", follow_redirects=True)
    assert "Welcome to myZiel" in r.text


def test_setup_only_once(user_client):
    r = user_client.post(
        "/setup", data={"email": "x@example.com", "password": "another-pass", "timezone": "UTC"}
    )
    assert r.headers["location"] == "/login"


def test_protected_pages_need_login(client):
    for path in ("/", "/goals", "/checkin", "/calendar", "/settings", "/account/export"):
        r = client.get(path)
        assert r.status_code == 303 and r.headers["location"] == "/login", path


def test_login_logout(user_client):
    user_client.post("/logout")
    assert user_client.get("/goals").headers["location"] == "/login"
    r = user_client.post("/login", data={"email": EMAIL, "password": "wrong-pass"})
    assert r.status_code == 401
    r = user_client.post("/login", data={"email": EMAIL, "password": "correct-horse"})
    assert r.status_code == 303
    assert user_client.get("/goals").status_code == 200


def test_login_is_rate_limited(user_client):
    user_client.post("/logout")
    for _ in range(5):
        user_client.post("/login", data={"email": EMAIL, "password": "nope-nope"})
    r = user_client.post("/login", data={"email": EMAIL, "password": "correct-horse"})
    assert r.status_code == 429


def test_profile_changes_are_versioned(user_client, session):
    user_client.post("/profile", data={"situation": "Job hunting"})
    user_client.post("/profile", data={"situation": "Job hunting"})  # unchanged: no new version
    user_client.post("/profile", data={"situation": "Working part-time"})
    r = user_client.get("/profile")
    assert "Working part-time" in r.text
    from myziel.modules.profile_goals.models import ProfileAnswer

    versions = session.scalars(select(ProfileAnswer.version)).all()
    assert sorted(versions) == [1, 2]


def test_goal_target_is_derived(user_client, session):
    add_goal(user_client)  # 5 per week, weekdays only
    v = session.scalar(select(GoalVersion))
    assert v.daily_target == 1
    assert "daily target 1" in user_client.get("/goals").text


def test_goal_validation_errors_are_shown(user_client):
    r = user_client.post(
        "/goals/new",
        data={"title": "Ship it", "goal_type": "outcome", "metric": "features", "unit": "count",
              "target_value": "3", "target_period": "total", "priority": "2", "status": "active"},
    )
    assert r.status_code == 422
    assert "deadline" in r.text


def test_active_goal_limit(user_client):
    for i in range(3):
        add_goal(user_client, title=f"Goal {i}")
    r = user_client.post(
        "/goals/new",
        data={"title": "One too many", "goal_type": "habit", "metric": "x", "unit": "count",
              "target_value": "1", "target_period": "day", "priority": "2", "status": "active"},
    )
    assert r.status_code == 422
    assert "active goals" in r.text


def test_full_checkin_flow_scores_green(user_client, session):
    add_goal(user_client)
    page = user_client.get("/checkin")
    assert "Check-in for Monday 05 October" in page.text
    assert "Today&#39;s target: 1" in page.text or "Today's target: 1" in page.text

    review = user_client.post("/checkin/review", data=checkin_form(goal_1="1"))
    assert review.status_code == 200
    assert "Submit and lock" in review.text

    r = submit(user_client, goal_1="1")
    assert r.headers["location"] == "/calendar/2026-10-05"

    score = session.scalar(select(DayScore))
    assert score.score == 100 and score.light == "green"
    checkin = session.scalar(select(CheckIn))
    assert not checkin.is_late
    assert checkin.raw_text == "Solid day"

    day = user_client.get("/calendar/2026-10-05")
    assert "On track" in day.text and "locked" in day.text
    cal = user_client.get("/calendar")
    assert "state-green" in cal.text
    home = user_client.get("/")
    assert "Checked in for Monday" in home.text


def test_partial_progress_is_red_or_amber(user_client, session):
    add_goal(user_client, title="Deep work", metric="focus", unit="hours", target_value="2",
             target_period="day", weekdays_only="")
    submit(user_client, goal_1="1.2")  # 60%
    assert session.scalar(select(DayScore.light)) == "amber"


def test_cannot_check_in_twice(user_client, session):
    add_goal(user_client)
    submit(user_client, goal_1="1")
    r = submit(user_client, goal_1="0")
    assert r.headers["location"] == "/checkin"
    assert len(session.scalars(select(CheckIn)).all()) == 1
    assert "already checked in" in user_client.get("/checkin").text


def test_change_answers_returns_to_form_without_saving(user_client, session):
    add_goal(user_client)
    r = user_client.post("/checkin/submit", data={**checkin_form(goal_1="1"), "action": "edit"})
    assert r.status_code == 200 and "Review answers" in r.text
    assert session.scalar(select(CheckIn)) is None


def test_window_closed_during_the_day(user_client, clock):
    add_goal(user_client)
    clock.set(utc(2026, 10, 5, 12, 0))  # 14:00 Berlin
    assert "window is closed" in user_client.get("/checkin").text
    r = submit(user_client, goal_1="1")
    assert r.headers["location"] == "/checkin"


def test_next_morning_submission_is_late(user_client, clock, session):
    add_goal(user_client)
    clock.set(utc(2026, 10, 6, 7, 0))  # Tue 09:00 Berlin -> still Monday's window
    submit(user_client, goal_1="1")
    checkin = session.scalar(select(CheckIn))
    assert checkin.local_date.isoformat() == "2026-10-05"
    assert checkin.is_late


def test_missed_day_is_grey(user_client, clock):
    add_goal(user_client)
    clock.set(utc(2026, 10, 7, 12, 0))  # Wednesday; Monday and Tuesday windows closed
    cal = user_client.get("/calendar?end=2026-10")
    assert cal.text.count("state-grey") >= 2


def test_weekend_with_weekday_goal_has_no_score(user_client, clock, session):
    add_goal(user_client)
    clock.set(utc(2026, 10, 10, 19, 0))  # Saturday
    submit(user_client, goal_1="0")
    score = session.scalar(select(DayScore))
    assert score.score is None and score.light == "none"


def test_editing_a_goal_never_changes_history(user_client, clock, session):
    add_goal(user_client)
    submit(user_client, goal_1="1")
    r = user_client.post(
        "/goals/1",
        data={"title": "Job applications", "goal_type": "habit", "metric": "applications",
              "unit": "count", "target_value": "10", "target_period": "week",
              "weekdays_only": "on", "priority": "3", "status": "active"},
    )
    assert r.status_code == 303
    versions = session.scalars(select(GoalVersion).order_by(GoalVersion.version)).all()
    assert [v.daily_target for v in versions] == [1, 2]

    session.expire_all()
    assert session.scalar(select(DayScore.score)) == 100
    day = user_client.get("/calendar/2026-10-05")
    assert "v1" in day.text and "100" in day.text

    # The next day uses version 2's target.
    clock.set(utc(2026, 10, 6, 19, 0))
    submit(user_client, goal_1="1")
    scores = session.scalars(select(DayScore.score).order_by(DayScore.local_date)).all()
    assert scores == [100, 50]


def test_amendment_is_shown(user_client):
    add_goal(user_client)
    submit(user_client, goal_1="1")
    user_client.post("/checkin/2026-10-05/amend", data={"note": "It was 2, not 1"})
    assert "It was 2, not 1" in user_client.get("/calendar/2026-10-05").text


def test_self_rating_calendar_mode(user_client):
    add_goal(user_client)
    submit(user_client, goal_1="0", self_rating="amber")  # computed red, self amber
    assert "state-red" in user_client.get("/calendar?mode=score").text
    assert "state-amber" in user_client.get("/calendar?mode=self").text


def test_dashboard_week_and_streak(user_client, clock):
    add_goal(user_client)
    for day in (5, 6, 7):
        clock.set(utc(2026, 10, day, 19, 0))
        submit(user_client, goal_1="1")
    home = user_client.get("/")
    assert "3 / 5" in home.text
    assert "<strong>3</strong>" in home.text  # check-in streak


def test_settings_and_export(user_client):
    r = user_client.post(
        "/settings",
        data={"timezone": "Europe/Berlin", "checkin_window_start": "19:00",
              "checkin_window_end": "09:00", "reminder_enabled": "on", "reminder_time": "20:30",
              "quiet_hours_start": "23:00", "quiet_hours_end": "07:00", "green_threshold": "85",
              "amber_threshold": "55", "max_active_goals": "4", "calendar_mode": "score"},
    )
    assert r.status_code == 303
    assert 'value="20:30"' in user_client.get("/settings").text

    add_goal(user_client)
    submit(user_client, goal_1="1")
    export = user_client.get("/account/export")
    data = json.loads(export.text)
    assert data["user"]["email"] == EMAIL
    assert len(data["checkins"]) == 1
    assert "password_hash" not in json.dumps(data)


def test_bad_settings_are_rejected(user_client):
    r = user_client.post(
        "/settings",
        data={"timezone": "Europe/Berlin", "checkin_window_start": "19:00",
              "checkin_window_end": "09:00", "reminder_time": "20:30",
              "quiet_hours_start": "23:00", "quiet_hours_end": "07:00", "green_threshold": "50",
              "amber_threshold": "80", "max_active_goals": "4"},
    )
    assert r.status_code == 303
    assert "Settings not saved" in user_client.get("/settings").text


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "db": "ok"}
    assert client.get("/metrics").json()["checkins_total"] == 0
