from datetime import date, timedelta

from myziel.modules.scoring.streaks import checkin_streak, productivity_streak

END = date(2026, 10, 20)


def days_back(*offsets: int) -> set[date]:
    return {END - timedelta(days=o) for o in offsets}


def test_consecutive_days():
    assert checkin_streak(days_back(0, 1, 2, 3), END) == 4


def test_nothing_submitted():
    assert checkin_streak(set(), END) == 0


def test_end_day_missing_means_zero():
    assert checkin_streak(days_back(1, 2), END) == 0


def test_single_gap_is_frozen():
    # gap at offset 2 is covered by a freeze; it does not count towards length
    assert checkin_streak(days_back(0, 1, 3, 4), END) == 4


def test_two_day_gap_breaks_streak():
    assert checkin_streak(days_back(0, 1, 4, 5), END) == 2


def test_only_one_freeze_per_7_days():
    # gaps at offsets 2 and 5 are 3 days apart: second gap ends the streak
    assert checkin_streak(days_back(0, 1, 3, 4, 6, 7), END) == 4


def test_freezes_7_days_apart_both_work():
    submitted = days_back(*[o for o in range(0, 12) if o not in (2, 9)])
    assert checkin_streak(submitted, END) == 10


def test_freezes_can_be_disabled():
    assert checkin_streak(days_back(0, 1, 3, 4), END, freeze_every_days=0) == 2


def test_productivity_streak_uses_green_threshold():
    scores = {END: 90.0, END - timedelta(days=1): 80.0, END - timedelta(days=2): 79.0,
              END - timedelta(days=3): None}
    assert productivity_streak(scores, END, freeze_every_days=0) == 2
    assert productivity_streak(scores, END, green_threshold=70, freeze_every_days=0) == 3
