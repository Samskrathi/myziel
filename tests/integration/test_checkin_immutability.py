"""Check-ins are append-only at database level (FR-2.5, FR-2.7, NFR-4, NFR-6)."""

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from myziel.modules.checkin.models import CheckIn, CheckInValue
from myziel.modules.checkin.service import verify_chain
from tests.conftest import PASSWORD, add_goal, checkin_form, utc


@pytest.fixture
def submitted(user_client, clock):
    add_goal(user_client)
    form = checkin_form(goal_1="1")
    r = user_client.post("/checkin/submit", data={**form, "action": "submit"})
    assert r.status_code == 303
    return user_client


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE checkin SET energy = 1",
        "DELETE FROM checkin",
        "UPDATE checkin_value SET value = 99",
        "DELETE FROM checkin_value",
    ],
)
def test_database_rejects_update_and_delete(submitted, app, sql):
    with app.state.engine.connect() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text(sql))


def test_amendments_are_append_only(submitted, app):
    r = submitted.post("/checkin/2026-10-05/amend", data={"note": "Actually 2 applications"})
    assert r.status_code == 303
    with app.state.engine.connect() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text("UPDATE checkin_amendment SET note = 'x'"))
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text("DELETE FROM checkin_amendment"))


def test_no_update_or_delete_endpoints(submitted):
    for method in ("put", "patch", "delete"):
        r = getattr(submitted, method)("/checkin/2026-10-05")
        assert r.status_code in (404, 405)


def test_hash_chain_links_records_and_detects_tampering(submitted, session, clock):
    clock.set(utc(2026, 10, 6, 19, 0))
    form = checkin_form(goal_1="0")
    submitted.post("/checkin/submit", data={**form, "action": "submit"})
    checkins = list(session.scalars(select(CheckIn).order_by(CheckIn.id)))
    assert len(checkins) == 2
    assert checkins[0].prev_hash is None
    assert checkins[1].prev_hash == checkins[0].hash
    assert verify_chain(checkins)
    checkins[0].energy = 1  # in memory only; never flushed
    assert not verify_chain(checkins)
    session.rollback()


def test_account_deletion_is_the_only_way_to_remove_checkins(submitted, app):
    r = submitted.post("/account/delete", data={"password": "wrong-password"})
    assert r.status_code == 303
    with app.state.sessionmaker() as s:
        assert s.scalar(select(func.count()).select_from(CheckIn)) == 1

    r = submitted.post("/account/delete", data={"password": PASSWORD})
    assert r.status_code == 303 and r.headers["location"] == "/setup"
    with app.state.sessionmaker() as s:
        assert s.scalar(select(func.count()).select_from(CheckIn)) == 0
        assert s.scalar(select(func.count()).select_from(CheckInValue)) == 0
