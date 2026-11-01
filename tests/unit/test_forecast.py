from datetime import date

import pytest

from myziel.modules.insights.forecast import days_behind, ewma, forecast_completion

TODAY = date(2026, 10, 1)


def test_ewma_of_constant_series():
    assert ewma([2, 2, 2, 2]) == 2


def test_ewma_weights_recent_values_more():
    assert ewma([0, 0, 0, 10]) > ewma([10, 0, 0, 0])


def test_ewma_empty():
    assert ewma([]) == 0


def test_constant_pace_projects_exact_date():
    f = forecast_completion([1.0] * 14, remaining=10, today=TODAY)
    assert f.pace_per_day == pytest.approx(1.0)
    assert f.projected == date(2026, 10, 11)
    assert f.optimistic == f.projected == f.pessimistic  # no variance


def test_variable_pace_gives_a_range():
    f = forecast_completion([0, 2] * 7, remaining=10, today=TODAY)
    assert f.optimistic is not None and f.projected is not None
    assert f.optimistic <= f.projected
    assert f.pessimistic is None or f.pessimistic >= f.projected


def test_zero_pace_has_no_projection():
    f = forecast_completion([0] * 14, remaining=5, today=TODAY)
    assert f.projected is None


def test_already_done():
    f = forecast_completion([1] * 3, remaining=0, today=TODAY)
    assert f.projected == TODAY


def test_only_last_14_days_count():
    old_zeros_then_fast = [0.0] * 30 + [2.0] * 14
    f = forecast_completion(old_zeros_then_fast, remaining=10, today=TODAY)
    assert f.pace_per_day == pytest.approx(2.0)


def test_days_behind():
    assert days_behind(date(2026, 10, 15), date(2026, 10, 10)) == 5
    assert days_behind(date(2026, 10, 5), date(2026, 10, 10)) == -5
    assert days_behind(None, date(2026, 10, 10)) is None
