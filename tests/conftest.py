"""Shared fixtures.

Every integration test gets a fresh SQLite file built by the real Alembic migration (so the
migration and its append-only triggers are tested too) and a FixedClock it can move.
"""

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from myziel.config import Settings
from myziel.core.clock import FixedClock
from myziel.main import create_app
from myziel.modules.notifications.channels.base import MemoryChannel

ROOT = Path(__file__).resolve().parents[1]
TZ = "Europe/Berlin"
PASSWORD = "correct-horse"
EMAIL = "me@example.com"


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


@pytest.fixture(scope="session")
def migrated_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("template") / "template.db"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    command.upgrade(cfg, "head")
    return path


@pytest.fixture
def db_url(migrated_db: Path, tmp_path: Path) -> str:
    path = tmp_path / "test.db"
    shutil.copy(migrated_db, path)
    return f"sqlite:///{path.as_posix()}"


@pytest.fixture
def clock() -> FixedClock:
    # Monday 5 Oct 2026, 19:00 UTC = 21:00 in Berlin: check-in window (18:00-10:00) is open.
    return FixedClock(utc(2026, 10, 5, 19, 0))


@pytest.fixture
def channel() -> MemoryChannel:
    return MemoryChannel()


@pytest.fixture
def app(db_url: str, clock: FixedClock, channel: MemoryChannel):  # type: ignore[no-untyped-def]
    settings = Settings(
        database_url=db_url, secret_key="test-secret", scheduler_enabled=False, smtp_url=""
    )
    application = create_app(settings, clock=clock, channel=channel)
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app) -> TestClient:  # type: ignore[no-untyped-def]
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def session(app):  # type: ignore[no-untyped-def]
    with app.state.sessionmaker() as s:
        yield s


@pytest.fixture
def user_client(client: TestClient) -> TestClient:
    """A client logged in as a freshly set-up user."""
    r = client.post("/setup", data={"email": EMAIL, "password": PASSWORD, "timezone": TZ})
    assert r.status_code == 303, r.text
    return client


def add_goal(client: TestClient, **overrides: object) -> None:
    data = {
        "title": "Job applications",
        "goal_type": "habit",
        "metric": "applications",
        "unit": "count",
        "target_value": "5",
        "target_period": "week",
        "weekdays_only": "on",
        "priority": "3",
        "status": "active",
    }
    data.update({k: str(v) for k, v in overrides.items()})
    r = client.post("/goals/new", data=data)
    assert r.status_code == 303, r.text


def checkin_form(**overrides: object) -> dict[str, str]:
    data = {
        "energy": "4",
        "mood": "3",
        "sleep_hours": "7.5",
        "blocker": "",
        "raw_text": "Solid day",
        "self_rating": "green",
    }
    data.update({k: str(v) for k, v in overrides.items()})
    return data
