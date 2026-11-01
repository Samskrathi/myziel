#!/bin/sh
# Restore a backup (NFR-8). Stop the app first.
# Usage: scripts/restore.sh <backup_file> [db_path]
set -eu
SRC="$1"
DB="${2:-data/myziel.db}"
PY="${PYTHON:-python}"
"$PY" -c "import sqlite3,sys; r=sqlite3.connect(sys.argv[1]).execute('PRAGMA integrity_check').fetchone()[0]; sys.exit(0 if r=='ok' else 1)" "$SRC"
if [ -f "$DB" ]; then
  cp "$DB" "$DB.before-restore"
  echo "Previous database kept at $DB.before-restore"
fi
cp "$SRC" "$DB"
echo "Restored $SRC -> $DB"
