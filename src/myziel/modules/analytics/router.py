"""Dashboard and calendar pages."""

from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from myziel.core.clock import Clock, get_clock, local_today
from myziel.core.db import get_db
from myziel.modules.analytics.calendar import shift_month
from myziel.modules.analytics.queries import dashboard, day_detail, month_cells
from myziel.modules.auth.models import User
from myziel.modules.auth.service import current_user, user_settings
from myziel.modules.profile_goals.service import list_goals
from myziel.web import redirect, render

router = APIRouter()

CALENDAR_MONTHS = 3  # FR-4.3: default window is the last 3 months


@router.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    if not list_goals(db, user):
        return redirect("/goals")
    data = dashboard(db, user, clock.now_utc())
    chart = {
        "labels": [d.strftime("%a %d") for d in data.days],
        "scores": data.scores,
        "lights": data.lights,
    }
    return render(request, "dashboard/index.html", user=user, d=data, chart=chart)


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(
    request: Request,
    end: str | None = None,
    mode: str | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    now = clock.now_utc()
    today = local_today(now, user.timezone)
    try:
        y, m = (int(x) for x in end.split("-")) if end else (today.year, today.month)
        date(y, m, 1)
    except ValueError:
        y, m = today.year, today.month
    mode = mode if mode in ("score", "self") else user_settings(user)["calendar_mode"]
    months = []
    for back in range(CALENDAR_MONTHS - 1, -1, -1):
        yy, mm = shift_month(y, m, -back)
        months.append(
            {"title": date(yy, mm, 1).strftime("%B %Y"),
             "weeks": month_cells(db, user, yy, mm, now, mode)}
        )
    prev_y, prev_m = shift_month(y, m, -1)
    next_y, next_m = shift_month(y, m, 1)
    has_next = (next_y, next_m) <= (today.year, today.month)
    return render(
        request,
        "calendar/month.html",
        user=user,
        months=months,
        mode=mode,
        prev=f"{prev_y}-{prev_m:02d}",
        next=f"{next_y}-{next_m:02d}" if has_next else None,
        end=f"{y}-{m:02d}",
    )


@router.get("/calendar/{day}", response_class=HTMLResponse)
def calendar_day(
    day: date,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    rec, breakdown = day_detail(db, user, day)
    return render(
        request, "calendar/day.html", user=user, day=day, rec=rec, breakdown=breakdown
    )
