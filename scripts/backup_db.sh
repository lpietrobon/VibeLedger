#!/usr/bin/env bash
# Backs up the VibeLedger SQLite database.
# Usage: backup_db.sh [db_path] [backup_dir]
#
# Suggested cron entry (daily at 03:00):
#   0 3 * * * /path/to/VibeLedger/scripts/backup_db.sh
#
# Keeps the last 30 backups by default. Set BACKUP_RETAIN_DAYS to change.

set -euo pipefail

DB_PATH="${1:-$HOME/.vibeledger/vibeledger.db}"
BACKUP_DIR="${2:-$HOME/.vibeledger/backups}"
RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-30}"

if [ ! -f "$DB_PATH" ]; then
    echo "error: database not found at $DB_PATH" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DEST="$BACKUP_DIR/vibeledger-$TIMESTAMP.db"

# Use sqlite3 .backup for a consistent snapshot (safe even under load).
if command -v sqlite3 &>/dev/null; then
    sqlite3 "$DB_PATH" ".backup '$DEST'"
else
    cp "$DB_PATH" "$DEST"
fi

echo "backup: $DEST ($(du -h "$DEST" | cut -f1))"

# Prune old backups
find "$BACKUP_DIR" -name 'vibeledger-*.db' -mtime +"$RETAIN_DAYS" -delete 2>/dev/null || true
