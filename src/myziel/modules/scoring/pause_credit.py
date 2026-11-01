"""Pause credit earning and ledger rules (FR-2.11). Pure functions."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PauseRules:
    min_score: float = 70
    hours_per_10_points: float = 0.5
    daily_cap: float = 1.5
    streak_bonus_every: int = 7
    streak_bonus_hours: float = 0.5
    balance_cap: float = 10.0


def earned_for_day(
    score: float | None, productivity_streak_length: int, rules: PauseRules = PauseRules()
) -> float:
    """Credit earned on one day.

    0.5 h per full 10 points above 70, capped at 1.5 h, plus 0.5 h on every 7th day of a
    productivity streak.
    """
    if score is None or score < rules.min_score:
        return 0.0
    steps = math.floor((score - rules.min_score) / 10)
    earned = min(steps * rules.hours_per_10_points, rules.daily_cap)
    if (
        rules.streak_bonus_every > 0
        and productivity_streak_length > 0
        and productivity_streak_length % rules.streak_bonus_every == 0
    ):
        earned += rules.streak_bonus_hours
    return earned


def apply_earning(balance: float, earned: float, rules: PauseRules = PauseRules()) -> float:
    return min(balance + earned, rules.balance_cap)


def apply_spend(balance: float, hours: float) -> float:
    if hours <= 0:
        raise ValueError("spend must be positive")
    if hours > balance:
        raise ValueError("not enough pause credit")
    return balance - hours
