#!/usr/bin/env bash
# Backup REVIVE Postgres. Intended for cron / on-call runbooks.
set -euo pipefail

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$OUT_DIR"

HOST="${POSTGRES_HOST:-localhost}"
PORT="${POSTGRES_PORT:-5432}"
USER="${POSTGRES_USER:-revive}"
DB="${POSTGRES_DB:-revive}"

pg_dump -h "$HOST" -p "$PORT" -U "$USER" -d "$DB" -Fc > "$OUT_DIR/revive_${STAMP}.dump"
echo "Wrote $OUT_DIR/revive_${STAMP}.dump"
