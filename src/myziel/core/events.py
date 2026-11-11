"""In-process event bus (e.g. CheckInSubmitted) keeping modules decoupled."""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class CheckInSubmitted:
    checkin_id: int
    user_id: int
    local_date: date


Handler = Callable[[Any, Session], None]


class EventBus:
    """Handlers run synchronously inside the publisher's transaction."""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: object, session: Session) -> None:
        for handler in self._handlers[type(event)]:
            handler(event, session)
