from datetime import date, timedelta

from myziel.modules.insights.drift import (
    extra_signals,
    is_behind,
    required_pace,
    rolling_pace,
    sustained,
)

TODAY = date(2026, 10, 20)


def test_rolling_pace_counts_missing_days_as_zero():
    values = {TODAY: 7.0}
    assert rolling_pace(values, TODAY) == 1.0


def test_rolling_pace_window():
    values = {TODAY - timedelta(days=i): 1.0 for i in range(10)}
    assert rolling_pace(values, TODAY) == 1.0


def test_required_pace():
    # 10 left, deadline in 4 days (today counts) -> 2 per day
    assert required_pace(10, TODAY, TODAY + timedelta(days=4)) == 2
    assert required_pace(0, TODAY, TODAY) == 0
    assert required_pace(5, TODAY, TODAY - timedelta(days=1)) == float("inf")


def test_behind_means_more_than_20_percent_below():
    assert not is_behind(0.8, 1.0)
    assert is_behind(0.79, 1.0)
    assert not is_behind(0, 0)


def test_needs_3_days_in_a_row():
    assert not sustained([True, True])
    assert not sustained([True, True, False])
    assert sustained([False, True, True, True])


def test_readme_example_gap():
    # "You need 1.4 h/day, you are averaging 0.9 h/day" -> drifting
    assert is_behind(0.9, 1.4)


def test_extra_signals():
    assert extra_signals(["green", "red", "red"], []) == ["2 red days in a row"]
    assert extra_signals(["grey", "grey"], []) == ["2 missed check-ins in a row"]
    assert extra_signals(["green"], ["Tired", "tired ", "TIRED", "meetings"]) == [
        "blocker 'tired' mentioned 3 times"
    ]
    assert extra_signals(["red", "green", "red"], []) == []
