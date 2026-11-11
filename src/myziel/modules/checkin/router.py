"""Daily check-in: form -> review (confirm values) -> submit (locked). Plus amendments."""

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from myziel.core.clock import Clock, get_clock
from myziel.core.db import get_db
from myziel.modules.auth.models import User
from myziel.modules.auth.service import current_user
from myziel.modules.checkin import repository
from myziel.modules.checkin.schemas import CheckInAnswers
from myziel.modules.checkin.service import (
    CheckInError,
    add_amendment,
    checkin_context,
    submit_checkin,
)
from myziel.web import flash, redirect, render

router = APIRouter()


async def _parse(request: Request, questions: list) -> tuple[CheckInAnswers | None, dict, str]:
    form = dict((await request.form()).items())
    goal_values = {}
    for q in questions:
        raw = form.get(q.key, "")
        if q.unit == "done":
            goal_values[q.goal_version_id] = 1.0 if raw in ("1", "on", "1.0") else 0.0
        else:
            goal_values[q.goal_version_id] = raw or 0
    try:
        answers = CheckInAnswers(
            energy=form.get("energy"),
            mood=form.get("mood"),
            sleep_hours=form.get("sleep_hours", ""),
            blocker=form.get("blocker", ""),
            raw_text=form.get("raw_text", ""),
            self_rating=form.get("self_rating"),
            goal_values=goal_values,
        )
    except ValidationError as exc:
        msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in exc.errors())
        return None, form, msg
    return answers, form, ""


@router.get("/checkin", response_class=HTMLResponse)
def checkin_form(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    ctx = checkin_context(db, user, clock.now_utc())
    return render(request, "checkin/form.html", user=user, ctx=ctx, form={})


@router.post("/checkin/review", response_class=HTMLResponse)
async def checkin_review(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    ctx = checkin_context(db, user, clock.now_utc())
    if ctx.day is None or ctx.already_submitted:
        return redirect("/checkin")
    answers, form, error = await _parse(request, ctx.questions)
    if answers is None:
        flash(request, error, "error")
        return render(request, "checkin/form.html", 422, user=user, ctx=ctx, form=form)
    return render(
        request, "checkin/review.html", user=user, ctx=ctx, answers=answers, form=form
    )


@router.post("/checkin/submit")
async def checkin_submit(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    ctx = checkin_context(db, user, clock.now_utc())
    answers, form, error = await _parse(request, ctx.questions)
    if answers is None:
        flash(request, error, "error")
        return redirect("/checkin")
    if form.get("action") == "edit":
        return render(request, "checkin/form.html", user=user, ctx=ctx, form=form)
    try:
        checkin = submit_checkin(db, request.app.state.bus, user, answers, clock.now_utc())
    except CheckInError as exc:
        flash(request, str(exc), "error")
        return redirect("/checkin")
    flash(request, "Check-in saved and locked.")
    return redirect(f"/calendar/{checkin.local_date.isoformat()}")


@router.post("/checkin/{day}/amend")
def checkin_amend(
    day: date,
    request: Request,
    note: str = Form(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    checkin = repository.get_by_date(db, user.id, day)
    if checkin is None:
        raise HTTPException(404)
    try:
        add_amendment(db, checkin, note, clock.now_utc())
    except CheckInError as exc:
        flash(request, str(exc), "error")
    else:
        flash(request, "Amendment added.")
    return redirect(f"/calendar/{day.isoformat()}")
