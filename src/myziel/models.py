"""Imports every model so Base.metadata is complete (used by Alembic and tests)."""

from myziel.core.db import Base
from myziel.modules.auth.models import AccountDeletion, User
from myziel.modules.checkin.models import CheckIn, CheckInAmendment, CheckInValue
from myziel.modules.notifications.models import Notification
from myziel.modules.profile_goals.models import Goal, GoalVersion, ProfileAnswer
from myziel.modules.scoring.models import DayScore

__all__ = [
    "AccountDeletion",
    "Base",
    "CheckIn",
    "CheckInAmendment",
    "CheckInValue",
    "DayScore",
    "Goal",
    "GoalVersion",
    "Notification",
    "ProfileAnswer",
    "User",
]
