"""Profile (onboarding interview) and goal pages."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from myziel.core.clock import Clock, get_clock
from myziel.core.db import get_db
from myziel.modules.auth.models import User
from myziel.modules.auth.service import current_user
from myziel.modules.profile_goals.schemas import PROFILE_QUESTIONS, GoalInput
from myziel.modules.profile_goals.service import (
    GoalLimitReached,
    create_goal,
    current_profile,
    get_goal,
    goal_to_input,
    list_goals,
    save_profile,
    update_goal,
)
from myziel.web import flash, redirect, render

router = APIRouter()


def _errors(exc: ValidationError) -> str:
    return "; ".join(
        (f"{e['loc'][-1]}: " if e["loc"] else "") + e["msg"].removeprefix("Value error, ")
        for e in exc.errors()
    )


async def _goal_form(request: Request) -> dict[str, Any]:
    form = dict((await request.form()).items())
    form["weekdays_only"] = form.get("weekdays_only") == "on"
    return form


@router.get("/profile", response_class=HTMLResponse)
def profile_form(
    request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    return render(
        request,
        "goals/profile.html",
        user=user,
        questions=PROFILE_QUESTIONS,
        answers=current_profile(db, user),
    )


@router.post("/profile")
async def profile_save(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    form = await request.form()
    answers = {k: str(form.get(k, "")) for k, _ in PROFILE_QUESTIONS}
    changed = save_profile(db, user, answers, clock.now_utc())
    flash(request, f"Profile saved ({changed} answer(s) changed).")
    return redirect("/goals" if not list_goals(db, user) else "/profile")


@router.get("/goals", response_class=HTMLResponse)
def goals_page(
    request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    return render(request, "goals/list.html", user=user, goals=list_goals(db, user))


@router.get("/goals/new", response_class=HTMLResponse)
def goal_new_form(request: Request, user: User = Depends(current_user)) -> Response:
    return render(request, "goals/form.html", user=user, goal=None, data={})


@router.post("/goals/new")
async def goal_create(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    form = await _goal_form(request)
    try:
        create_goal(db, user, GoalInput(**form), clock.now_utc())
    except ValidationError as exc:
        flash(request, _errors(exc), "error")
        return render(request, "goals/form.html", 422, user=user, goal=None, data=form)
    except GoalLimitReached as exc:
        flash(request, str(exc), "error")
        return render(request, "goals/form.html", 422, user=user, goal=None, data=form)
    flash(request, "Goal created.")
    return redirect("/goals")


def _owned_goal(db: Session, user: User, goal_id: int):  # type: ignore[no-untyped-def]
    goal = get_goal(db, user, goal_id)
    if goal is None:
        raise HTTPException(404)
    return goal


@router.get("/goals/{goal_id}", response_class=HTMLResponse)
def goal_edit_form(
    goal_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    goal = _owned_goal(db, user, goal_id)
    data = goal_to_input(goal.current).model_dump()
    return render(request, "goals/form.html", user=user, goal=goal, data=data)


@router.post("/goals/{goal_id}")
async def goal_update(
    goal_id: int,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    clock: Clock = Depends(get_clock),
) -> Response:
    goal = _owned_goal(db, user, goal_id)
    form = await _goal_form(request)
    try:
        update_goal(db, user, goal, GoalInput(**form), clock.now_utc())
    except ValidationError as exc:
        flash(request, _errors(exc), "error")
        return render(request, "goals/form.html", 422, user=user, goal=goal, data=form)
    except GoalLimitReached as exc:
        flash(request, str(exc), "error")
        return render(request, "goals/form.html", 422, user=user, goal=goal, data=form)
    flash(request, f"Goal saved as version {goal.current.version}.")
    return redirect("/goals")
