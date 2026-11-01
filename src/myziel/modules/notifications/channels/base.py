"""Channel interface so new channels plug in (FR-6.2)."""

from typing import Protocol


class Channel(Protocol):
    name: str

    def send(self, to: str, subject: str, body: str) -> None:
        """Deliver a message. Raise on failure."""
        ...


class MemoryChannel:
    """Collects messages instead of sending them (tests, local dev)."""

    name = "memory"

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))
