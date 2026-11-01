from datetime import date

import pytest

from myziel.modules.profile_goals.targets import (
    count_active_days,
    derive_daily_target,
    target_for_day,
)


def test_week_target_over_weekdays_is_one_per_weekday():
    # README example: 5 applications per week becomes 1 per weekday
    assert derive_daily_target(5, "week", weekdays_only=True) == 1


def test_week_target_over_all_days():
    assert derive_daily_target(7, "week") == 1


def test_day_target_is_unchanged():
    assert derive_daily_target(2.5, "day") == 2.5


def test_total_target_spread_until_deadline():
    # 1 Oct .. 10 Oct inclusive = 10 days
    d = derive_daily_target(20, "total", start=date(2026, 10, 1), deadline=date(2026, 10, 10))
    assert d == 2


def test_total_target_weekdays_only():
    # Mon 5 Oct .. Sun 11 Oct = 5 weekdays
    d = derive_daily_target(
        10, "total", weekdays_only=True, start=date(2026, 10, 5), deadline=date(2026, 10, 11)
    )
    assert d == 2


def test_total_target_needs_deadline():
    with pytest.raises(ValueError):
        derive_daily_target(10, "total", start=date(2026, 10, 5))


def test_deadline_in_past_is_rejected():
    with pytest.raises(ValueError):
        derive_daily_target(10, "total", start=date(2026, 10, 5), deadline=date(2026, 10, 1))


def test_weekend_target_is_zero_for_weekday_goals():
    saturday = date(2026, 10, 10)
    assert target_for_day(1, saturday, weekdays_only=True) == 0
    assert target_for_day(1, saturday, weekdays_only=False) == 1


def test_count_active_days():
    assert count_active_days(date(2026, 10, 5), date(2026, 10, 18), True) == 10
    assert count_active_days(date(2026, 10, 5), date(2026, 10, 4), False) == 0
