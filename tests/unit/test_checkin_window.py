from datetime import date, datetime, time

from myziel.modules.checkin.service import (
    is_late,
    is_missed,
    open_checkin_date,
    record_hash,
    window_closes_at,
)

START, END = time(18, 0), time(10, 0)  # default overnight window
MON = date(2026, 10, 5)


def at(day: int, hh: int, mm: int = 0) -> datetime:
    return datetime(2026, 10, day, hh, mm)


def test_evening_belongs_to_today():
    assert open_checkin_date(at(5, 18), START, END) == MON
    assert open_checkin_date(at(5, 23, 59), START, END) == MON


def test_next_morning_belongs_to_yesterday_and_is_late():
    assert open_checkin_date(at(6, 9, 59), START, END) == MON
    assert is_late(MON, at(6, 9, 59))
    assert not is_late(MON, at(5, 22))


def test_daytime_is_closed():
    assert open_checkin_date(at(5, 10), START, END) is None
    assert open_checkin_date(at(5, 17, 59), START, END) is None


def test_same_day_window():
    s, e = time(6, 0), time(23, 0)
    assert open_checkin_date(at(5, 6), s, e) == MON
    assert open_checkin_date(at(5, 23), s, e) is None
    assert window_closes_at(MON, s, e) == at(5, 23)


def test_missed_only_after_window_closes():
    assert window_closes_at(MON, START, END) == at(6, 10)
    assert not is_missed(MON, at(6, 9, 59), START, END, submitted=False)
    assert is_missed(MON, at(6, 10), START, END, submitted=False)
    assert not is_missed(MON, at(7, 12), START, END, submitted=True)


def test_hash_depends_on_previous_hash_and_payload():
    h1 = record_hash(None, {"a": 1})
    assert h1 == record_hash(None, {"a": 1})
    assert h1 != record_hash("x", {"a": 1})
    assert h1 != record_hash(None, {"a": 2})
