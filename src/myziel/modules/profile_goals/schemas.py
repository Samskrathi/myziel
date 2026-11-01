"""Pydantic request/response models."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class GoalInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    why: str = ""
    goal_type: Literal["outcome", "habit"]
    metric: str = Field(min_length=1, max_length=100)
    unit: Literal["count", "hours", "minutes", "done"]
    target_value: float = Field(gt=0)
    target_period: Literal["day", "week", "total"]
    weekdays_only: bool = False
    deadline: date | None = None
    weekly_budget_hours: float | None = Field(default=None, ge=0)
    priority: int = Field(default=2, ge=1, le=3)
    status: Literal["active", "paused", "achieved", "abandoned"] = "active"
    daily_target_override: float | None = Field(default=None, gt=0)

    @field_validator("deadline", "weekly_budget_hours", "daily_target_override", mode="before")
    @classmethod
    def blank_is_none(cls, v: object) -> object:
        return None if v == "" else v

    @model_validator(mode="after")
    def check_consistency(self) -> "GoalInput":
        if self.target_period == "total" and self.deadline is None:
            raise ValueError("A total target needs a deadline")
        if self.goal_type == "outcome" and self.deadline is None:
            raise ValueError("Outcome goals need a deadline")
        if self.unit == "done" and self.target_period == "day" and self.target_value != 1:
            raise ValueError("A done/not-done goal has a daily target of 1")
        return self


PROFILE_QUESTIONS: list[tuple[str, str]] = [
    ("situation", "What is your role or life situation right now?"),
    ("working_hours", "What are your typical working hours?"),
    ("energy_peaks", "When in the day do you have the most energy?"),
    ("commitments", "What fixed commitments do you have each week?"),
    ("derailers", "What usually derails you?"),
]
