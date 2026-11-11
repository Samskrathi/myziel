"""Validated check-in answers (structured form, FR-2.8)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CheckInAnswers(BaseModel):
    energy: int = Field(ge=1, le=5)
    mood: int = Field(ge=1, le=5)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    blocker: str = Field(default="", max_length=500)
    raw_text: str = Field(default="", max_length=5000)
    self_rating: Literal["green", "amber", "red"]
    goal_values: dict[int, float] = Field(default_factory=dict)  # goal_version_id -> value

    @field_validator("sleep_hours", mode="before")
    @classmethod
    def blank_is_none(cls, v: object) -> object:
        return None if v == "" else v

    @field_validator("goal_values")
    @classmethod
    def non_negative(cls, v: dict[int, float]) -> dict[int, float]:
        if any(x < 0 for x in v.values()):
            raise ValueError("Values cannot be negative")
        return v
