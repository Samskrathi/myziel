"""Structured logging setup (NFR-10)."""

import logging
from typing import Any

import structlog


def setup_logging(level: str = "INFO", json: bool = False) -> None:
    logging.basicConfig(format="%(message)s", level=level)
    renderer: Any = (
        structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
    )


def get_logger(name: str = "myziel") -> Any:
    return structlog.get_logger(name)
