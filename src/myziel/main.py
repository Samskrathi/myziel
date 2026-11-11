"""FastAPI app factory: wires routers, event handlers and the scheduler."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from myziel.config import Settings, get_settings
from myziel.core.clock import Clock
from myziel.core.db import make_engine, make_sessionmaker
from myziel.core.events import EventBus
from myziel.core.logging import get_logger, setup_logging
from myziel.core.security import LoginRateLimiter
from myziel.modules.analytics.router import router as analytics_router
from myziel.modules.auth.router import router as auth_router
from myziel.modules.auth.service import LoginRequired
from myziel.modules.checkin.router import router as checkin_router
from myziel.modules.health.router import router as health_router
from myziel.modules.notifications.channels.base import Channel
from myziel.modules.notifications.channels.email import EmailChannel
from myziel.modules.notifications.scheduler import start_scheduler
from myziel.modules.profile_goals.router import router as goals_router
from myziel.modules.scoring import handlers as scoring_handlers
from myziel.web import WEB_DIR, redirect

log = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    channel: Channel | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_json)
    if settings.secret_key == "change-me":
        log.warning("config.default_secret_key", hint="set SECRET_KEY in .env")

    engine = make_engine(settings.database_url)
    make_session = make_sessionmaker(engine)
    clock = clock or Clock()
    channel = channel or EmailChannel(settings.smtp_url, settings.mail_from)

    bus = EventBus()
    scoring_handlers.register(bus)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        scheduler = None
        if settings.scheduler_enabled:
            scheduler = start_scheduler(
                make_session, clock, channel, settings.reminder_check_minutes
            )
        yield
        if scheduler:
            scheduler.shutdown(wait=False)
        engine.dispose()

    app = FastAPI(title="myZiel", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = make_session
    app.state.clock = clock
    app.state.bus = bus
    app.state.channel = channel
    app.state.login_limiter = LoginRateLimiter()

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="myziel_session",
        same_site="lax",
        https_only=settings.session_https_only,
        max_age=60 * 60 * 24 * 30,
    )

    @app.exception_handler(LoginRequired)
    async def _login_required(_request: Request, _exc: LoginRequired) -> Response:
        return redirect("/login")

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    for r in (health_router, auth_router, goals_router, checkin_router, analytics_router):
        app.include_router(r)
    return app


def app() -> FastAPI:
    """Factory for `uvicorn myziel.main:app --factory`."""
    return create_app()
