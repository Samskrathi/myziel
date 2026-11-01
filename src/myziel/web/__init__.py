"""Shared Jinja2 setup and small helpers for server-rendered pages."""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from myziel.modules.analytics.calendar import ICONS, LABELS
from myziel.modules.checkin.questions import unit_label

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")
templates.env.globals.update(ICONS=ICONS, LABELS=LABELS, unit_label=unit_label, zip=zip)


def fmt_num(value: float | None) -> str:
    if value is None:
        return "–"
    return f"{value:.2f}".rstrip("0").rstrip(".")


templates.env.filters["num"] = fmt_num


def flash(request: Request, message: str, kind: str = "info") -> None:
    # Reassign (not append in place) so the session notices the change.
    request.session["flash"] = [*request.session.get("flash", []), {"kind": kind, "text": message}]


def render(
    request: Request, name: str, status_code: int = 200, **context: Any
) -> HTMLResponse:
    messages = request.session.pop("flash", [])
    return templates.TemplateResponse(
        request, name, {"messages": messages, **context}, status_code=status_code
    )


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)
