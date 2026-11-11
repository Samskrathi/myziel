"""Public demo mode: seeded data, password-free entry, destructive actions blocked."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from myziel.config import Settings
from myziel.core.clock import FixedClock
from myziel.demo import DEMO_DAYS
from myziel.main import create_app
from myziel.modules.checkin.models import CheckIn
from myziel.modules.checkin.service import verify_chain
from myziel.modules.notifications.channels.base import MemoryChannel


def _demo_app(db_url: str, clock: FixedClock):  # type: ignore[no-untyped-def]
    settings = Settings(database_url=db_url, secret_key="test-secret", scheduler_enabled=False,
                        smtp_url="", demo_mode=True)
    return create_app(settings, clock=clock, channel=MemoryChannel())


def test_demo_seeds_and_lets_visitors_in(db_url: str, clock: FixedClock) -> None:
    app = _demo_app(db_url, clock)
    with TestClient(app, follow_redirects=False) as client:
        with app.state.sessionmaker() as s:
            count = s.scalar(select(func.count()).select_from(CheckIn)) or 0
            assert DEMO_DAYS * 0.8 < count <= DEMO_DAYS
            assert verify_chain(list(s.scalars(select(CheckIn).order_by(CheckIn.id))))

        assert client.get("/").headers["location"] == "/demo"
        assert client.get("/login").headers["location"] == "/demo"
        assert client.get("/demo").headers["location"] == "/"
        home = client.get("/")
        assert home.status_code == 200 and "Demo mode" in home.text
        assert client.get("/calendar").status_code == 200

        settings_page = client.get("/settings").text
        assert "Delete account" not in settings_page
        r = client.post("/account/delete", data={"password": "x"})
        assert r.status_code == 303 and r.headers["location"] == "/settings"
        assert client.get("/").status_code == 200  # still there

        # Today's check-in is open for visitors.
        assert "check" in client.get("/checkin").text.lower()
    app.state.engine.dispose()


def test_demo_seeding_runs_once(db_url: str, clock: FixedClock) -> None:
    for _ in range(2):
        app = _demo_app(db_url, clock)
        with TestClient(app):
            pass
        app.state.engine.dispose()
    with _demo_app(db_url, clock).state.sessionmaker() as s:
        assert (s.scalar(select(func.count()).select_from(CheckIn)) or 0) <= DEMO_DAYS
