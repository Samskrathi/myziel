"""Health endpoint and basic metrics (NFR-10)."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from myziel.core.db import get_db
from myziel.modules.checkin.models import CheckIn
from myziel.modules.notifications.models import Notification

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> JSONResponse:
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse({"status": "error", "db": "unreachable"}, status_code=503)
    return JSONResponse({"status": "ok", "db": "ok"})


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict[str, int]:
    def count(model: type) -> int:
        return db.scalar(select(func.count()).select_from(model)) or 0

    return {"checkins_total": count(CheckIn), "notifications_total": count(Notification)}
