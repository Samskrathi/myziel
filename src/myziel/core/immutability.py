"""Database-level append-only guard for check-ins (FR-2.7, NFR-4).

UPDATE is always rejected. DELETE is rejected unless the owner has a row in
`account_deletion`, which is the single exception allowed by NFR-6.
"""

from sqlalchemy import Connection, text

_CHILD_TABLES = ("checkin_value", "checkin_amendment")

_SQLITE = [
    """CREATE TRIGGER IF NOT EXISTS checkin_no_update BEFORE UPDATE ON checkin
       BEGIN SELECT RAISE(ABORT, 'checkin is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS checkin_no_delete BEFORE DELETE ON checkin
       WHEN NOT EXISTS (SELECT 1 FROM account_deletion WHERE user_id = OLD.user_id)
       BEGIN SELECT RAISE(ABORT, 'checkin is append-only'); END""",
]
for _t in _CHILD_TABLES:
    _SQLITE += [
        f"""CREATE TRIGGER IF NOT EXISTS {_t}_no_update BEFORE UPDATE ON {_t}
            BEGIN SELECT RAISE(ABORT, '{_t} is append-only'); END""",
        f"""CREATE TRIGGER IF NOT EXISTS {_t}_no_delete BEFORE DELETE ON {_t}
            WHEN NOT EXISTS (SELECT 1 FROM account_deletion d JOIN checkin c
                             ON c.user_id = d.user_id WHERE c.id = OLD.checkin_id)
            BEGIN SELECT RAISE(ABORT, '{_t} is append-only'); END""",
    ]

_POSTGRES = [
    """CREATE OR REPLACE FUNCTION myziel_reject_update() RETURNS trigger
       LANGUAGE plpgsql AS $fn$ BEGIN
         RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
       END $fn$""",
    """CREATE OR REPLACE FUNCTION myziel_guard_checkin_delete() RETURNS trigger
       LANGUAGE plpgsql AS $fn$ BEGIN
         IF NOT EXISTS (SELECT 1 FROM account_deletion WHERE user_id = OLD.user_id) THEN
           RAISE EXCEPTION 'checkin is append-only';
         END IF;
         RETURN OLD;
       END $fn$""",
    """CREATE OR REPLACE FUNCTION myziel_guard_child_delete() RETURNS trigger
       LANGUAGE plpgsql AS $fn$ BEGIN
         IF NOT EXISTS (SELECT 1 FROM account_deletion d JOIN checkin c
                        ON c.user_id = d.user_id WHERE c.id = OLD.checkin_id) THEN
           RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
         END IF;
         RETURN OLD;
       END $fn$""",
]
for _t, _guard in (
    ("checkin", "myziel_guard_checkin_delete"),
    ("checkin_value", "myziel_guard_child_delete"),
    ("checkin_amendment", "myziel_guard_child_delete"),
):
    _POSTGRES += [
        f"DROP TRIGGER IF EXISTS {_t}_no_update ON {_t}",
        f"""CREATE TRIGGER {_t}_no_update BEFORE UPDATE ON {_t}
            FOR EACH ROW EXECUTE FUNCTION myziel_reject_update()""",
        f"DROP TRIGGER IF EXISTS {_t}_no_delete ON {_t}",
        f"""CREATE TRIGGER {_t}_no_delete BEFORE DELETE ON {_t}
            FOR EACH ROW EXECUTE FUNCTION {_guard}()""",
    ]


def install_append_only_triggers(conn: Connection) -> None:
    dialect = conn.dialect.name
    if dialect == "sqlite":
        statements = _SQLITE
    elif dialect == "postgresql":
        statements = _POSTGRES
    else:
        raise RuntimeError(f"No append-only triggers for dialect {dialect}")
    for stmt in statements:
        conn.execute(text(stmt))
