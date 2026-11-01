import pytest

from myziel.modules.scoring.day_score import GoalProgress, day_score, goal_progress, traffic_light


def test_progress_is_capped_at_120_percent():
    assert goal_progress(5, 1) == 1.2
    assert goal_progress(0.5, 1) == 0.5


def test_progress_needs_positive_target():
    with pytest.raises(ValueError):
        goal_progress(1, 0)


def test_all_targets_met_is_100():
    assert day_score([GoalProgress(1, 1), GoalProgress(2, 2)]) == 100


def test_overachieving_one_goal_cannot_push_score_above_100():
    assert day_score([GoalProgress(10, 1), GoalProgress(10, 1)]) == 100


def test_overachieving_partly_compensates_another_goal():
    # (1.2 + 0.6) / 2 = 0.9
    assert day_score([GoalProgress(3, 1), GoalProgress(0.6, 1)]) == 90


def test_weighted_by_priority():
    # high priority goal (3) met, low (1) missed -> 3/4 = 75
    assert day_score([GoalProgress(1, 1, weight=3), GoalProgress(0, 1, weight=1)]) == 75


def test_goals_without_target_today_are_ignored():
    assert day_score([GoalProgress(1, 1), GoalProgress(0, 0)]) == 100


def test_no_counted_goals_gives_none():
    assert day_score([GoalProgress(0, 0)]) is None
    assert day_score([]) is None


@pytest.mark.parametrize(
    "score, light",
    [(100, "green"), (80, "green"), (79.9, "amber"), (50, "amber"), (49.9, "red"), (0, "red"),
     (None, "none")],
)
def test_traffic_light_default_thresholds(score, light):
    assert traffic_light(score) == light


def test_traffic_light_custom_thresholds():
    assert traffic_light(70, green=70, amber=40) == "green"
    assert traffic_light(39, green=70, amber=40) == "red"
