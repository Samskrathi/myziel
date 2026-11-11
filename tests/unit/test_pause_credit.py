import pytest

from myziel.modules.scoring.pause_credit import (
    PauseRules,
    apply_earning,
    apply_spend,
    earned_for_day,
)


@pytest.mark.parametrize(
    "score, hours",
    [(None, 0), (69.9, 0), (70, 0), (79, 0), (80, 0.5), (89, 0.5), (90, 1.0), (100, 1.5)],
)
def test_earning_per_10_points_above_70(score, hours):
    assert earned_for_day(score, productivity_streak_length=1) == hours


def test_daily_cap():
    rules = PauseRules(hours_per_10_points=1.0)
    assert earned_for_day(100, 1, rules) == 1.5


def test_streak_bonus_on_every_7th_day():
    assert earned_for_day(80, 7) == 1.0
    assert earned_for_day(80, 14) == 1.0
    assert earned_for_day(80, 8) == 0.5


def test_no_bonus_below_threshold_even_on_7th_day():
    assert earned_for_day(60, 7) == 0


def test_balance_is_capped():
    assert apply_earning(9.5, 1.5) == 10
    assert apply_earning(2, 1) == 3


def test_spend():
    assert apply_spend(3, 1.5) == 1.5
    with pytest.raises(ValueError):
        apply_spend(1, 2)
    with pytest.raises(ValueError):
        apply_spend(1, 0)
