from datetime import date

from myziel.modules.analytics.calendar import day_state, month_weeks, shift_month

TODAY = date(2026, 10, 20)
FIRST = date(2026, 10, 1)


def state(day: date, light=None, missed=False, open_day=TODAY):
    return day_state(
        day, light=light, open_day=open_day, local_today=TODAY, missed=missed, first_day=FIRST
    )


def test_month_weeks_start_on_monday_and_cover_month():
    weeks = month_weeks(2026, 10)
    assert weeks[0][0].weekday() == 0
    days = {d for w in weeks for d in w}
    assert date(2026, 10, 1) in days and date(2026, 10, 31) in days


def test_states():
    assert state(date(2026, 10, 10), light="green") == "green"
    assert state(date(2026, 10, 10), missed=True) == "grey"
    assert state(TODAY) == "pending"
    assert state(date(2026, 10, 25)) == "future"
    assert state(date(2026, 9, 30), missed=True) == "before"


def test_shift_month():
    assert shift_month(2026, 1, -1) == (2025, 12)
    assert shift_month(2026, 12, 1) == (2027, 1)
    assert shift_month(2026, 10, -2) == (2026, 8)
