#!/bin/sh
# Daily database backup (NFR-8). SQLite only; for PostgreSQL use pg_dump.
# Usage: scripts/backup.sh [db_path] [backup_dir] [keep_days]
# Cron example: 0 3 * * * cd /app && scripts/backup.sh
set -eu
DB="${1:-data/myziel.db}"
DIR="${2:-data/backups}"
KEEP="${3:-30}"
PY="${PYTHON:-python}"
mkdir -p "$DIR"
OUT="$DIR/myziel-$(date -u +%Y%m%dT%H%M%SZ).db"
# The sqlite backup API makes a consistent copy even while the app is writing.
"$PY" -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" "$DB" "$OUT"
"$PY" -c "import sqlite3,sys; r=sqlite3.connect(sys.argv[1]).execute('PRAGMA integrity_check').fetchone()[0]; sys.exit(0 if r=='ok' else 1)" "$OUT"
find "$DIR" -name 'myziel-*.db' -mtime +"$KEEP" -delete
echo "$OUT"
