"""APScheduler jobs: check-in reminders (timezone aware). More job types arrive in phase 2."""

from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from myziel.core.clock import Clock, parse_hhmm, to_local
from myziel.core.logging import get_logger
from myziel.modules.auth.models import User
from myziel.modules.auth.service import user_settings
from myziel.modules.checkin import repository
from myziel.modules.checkin.service import open_checkin_date
from myziel.modules.notifications.channels.base import Channel
from myziel.modules.notifications.models import Notification
from myziel.modules.notifications.policy import should_send_checkin_reminder

log = get_logger(__name__)

REMINDER = "checkin_reminder"


def _sent_today(session: Session, user_id: int, day: date) -> list[str]:
    return list(
        session.scalars(
            select(Notification.type).where(
                Notification.user_id == user_id,
                Notification.local_date == day,
                Notification.status == "sent",
            )
        )
    )


def run_reminders(make_session: sessionmaker[Session], clock: Clock, channel: Channel) -> int:
    """Send due check-in reminders. Returns how many were sent."""
    now = clock.now_utc()
    sent = 0
    with make_session() as session:
        for user in session.scalars(select(User)):
            s = user_settings(user)
            local_now = to_local(now, user.timezone)
            today = local_now.date()
            open_day = open_checkin_date(
                local_now,
                parse_hhmm(s["checkin_window_start"]),
                parse_hhmm(s["checkin_window_end"]),
            )
            sent_types = _sent_today(session, user.id, today)
            if not should_send_checkin_reminder(
                enabled=bool(s["reminder_enabled"]),
                local_time=local_now.time(),
                reminder_time=parse_hhmm(s["reminder_time"]),
                open_day=open_day,
                local_today=today,
                already_checked_in=repository.get_by_date(session, user.id, today) is not None,
                reminder_sent_today=REMINDER in sent_types,
                sent_today_count=len(sent_types),
                max_per_day=int(s["max_notifications_per_day"]),
                quiet_start=parse_hhmm(s["quiet_hours_start"]),
                quiet_end=parse_hhmm(s["quiet_hours_end"]),
            ):
                continue
            status, detail = "sent", ""
            try:
                channel.send(
                    user.email,
                    "myZiel: time for your daily check-in",
                    "Your check-in for today is open. It takes about 5 minutes.",
                )
                sent += 1
            except Exception as exc:  # noqa: BLE001 - record and move on to the next user
                status, detail = "failed", str(exc)
                log.warning("reminder.failed", user_id=user.id, error=detail)
            session.add(
                Notification(
                    user_id=user.id,
                    type=REMINDER,
                    channel=channel.name,
                    local_date=today,
                    sent_at=now,
                    status=status,
                    detail=detail,
                )
            )
            session.commit()
    return sent


def count_sent(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Notification)) or 0


def start_scheduler(
    make_session: sessionmaker[Session], clock: Clock, channel: Channel, every_minutes: int
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_reminders,
        "interval",
        minutes=every_minutes,
        args=[make_session, clock, channel],
        id="checkin_reminders",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("scheduler.started", every_minutes=every_minutes)
    return scheduler
