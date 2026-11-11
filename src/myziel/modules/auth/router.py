"""Setup, login, logout, settings, export and account deletion pages."""

import json
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from myziel.core.clock import Clock, get_clock, parse_hhmm
from myziel.core.db import get_db
from myziel.core.security import verify_password
from myziel.modules.auth.models import User
from myziel.modules.auth.service import (
    authenticate,
    create_user,
    current_user,
    delete_account,
    export_user_data,
    update_settings,
    user_count,
    user_settings,
    validate_timezone,
)
from myziel.web import flash, redirect, render

router = APIRouter()

TIMEZONES = sorted(available_timezones())


@router.get("/setup", response_class=HTMLResponse)
def setup_form(request: Request, db: Session = Depends(get_db)) -> Response:
    if user_count(db) > 0:
        return redirect("/login")
    return render(request, "auth/setup.html", timezones=TIMEZONES)


@router.post("/setup")
def setup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    timezone: str = Form(...),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    # v1 is single-user: setup only works while no account exists.
    if user_count(db) > 0:
        return redirect("/login")
    try:
        user = create_user(db, email, password, timezone, clock.now_utc())
    except ValueError as exc:
        flash(request, str(exc), "error")
        return redirect("/setup")
    request.session["user_id"] = user.id
    flash(request, "Account created. Tell us a little about yourself.")
    return redirect("/profile")


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)) -> Response:
    if user_count(db) == 0:
        return redirect("/setup")
    return render(request, "auth/login.html")


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> Response:
    limiter = request.app.state.login_limiter
    key = request.client.host if request.client else "unknown"
    if limiter.is_blocked(key):
        flash(request, "Too many failed attempts. Try again in 15 minutes.", "error")
        return render(request, "auth/login.html", status_code=429)
    user = authenticate(db, email, password)
    if user is None:
        limiter.record_failure(key)
        flash(request, "Wrong email or password.", "error")
        return render(request, "auth/login.html", status_code=401)
    limiter.reset(key)
    request.session.clear()
    request.session["user_id"] = user.id
    return redirect("/")


@router.post("/logout")
def logout(request: Request) -> Response:
    request.session.clear()
    return redirect("/login")


@router.get("/settings", response_class=HTMLResponse)
def settings_form(request: Request, user: User = Depends(current_user)) -> Response:
    return render(
        request, "auth/settings.html", user=user, s=user_settings(user), timezones=TIMEZONES
    )


@router.post("/settings")
async def save_settings(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    form = await request.form()
    try:
        tz = validate_timezone(str(form.get("timezone", user.timezone)))
        changes = {
            "checkin_window_start": str(form["checkin_window_start"]),
            "checkin_window_end": str(form["checkin_window_end"]),
            "reminder_enabled": form.get("reminder_enabled") == "on",
            "reminder_time": str(form["reminder_time"]),
            "quiet_hours_start": str(form["quiet_hours_start"]),
            "quiet_hours_end": str(form["quiet_hours_end"]),
            "green_threshold": int(str(form["green_threshold"])),
            "amber_threshold": int(str(form["amber_threshold"])),
            "max_active_goals": int(str(form["max_active_goals"])),
            "calendar_mode": str(form.get("calendar_mode", "score")),
        }
        for key in ("checkin_window_start", "checkin_window_end", "reminder_time",
                    "quiet_hours_start", "quiet_hours_end"):
            parse_hhmm(changes[key])
        if not 0 < changes["amber_threshold"] < changes["green_threshold"] <= 100:
            raise ValueError("Thresholds must satisfy 0 < amber < green <= 100")
        if not 1 <= changes["max_active_goals"] <= 5:
            raise ValueError("Active goal limit must be between 1 and 5")
        if changes["calendar_mode"] not in ("score", "self"):
            raise ValueError("Unknown calendar mode")
    except (KeyError, ValueError) as exc:
        flash(request, f"Settings not saved: {exc}", "error")
        return redirect("/settings")
    user.timezone = tz
    update_settings(db, user, changes)
    flash(request, "Settings saved.")
    return redirect("/settings")


@router.get("/account/export")
def export(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Response:
    body = json.dumps(export_user_data(db, user), indent=2, default=str)
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="myziel-export.json"'},
    )


@router.post("/account/delete")
def delete(
    request: Request,
    password: str = Form(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    if not verify_password(password, user.password_hash):
        flash(request, "Password incorrect; account not deleted.", "error")
        return redirect("/settings")
    delete_account(db, user, clock.now_utc())
    request.session.clear()
    return redirect("/setup")
