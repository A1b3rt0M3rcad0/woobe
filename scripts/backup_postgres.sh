#!/bin/sh
set -eu

: "${WOOBE_POSTGRES_URL:?WOOBE_POSTGRES_URL is required}"
: "${BACKUP_DIR:=/backups}"

umask 077
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$BACKUP_DIR/woobe-$timestamp.dump"
temporary="$backup.partial"

pg_dump \
  --dbname "$WOOBE_POSTGRES_URL" \
  --format custom \
  --compress 9 \
  --no-owner \
  --no-acl \
  --file "$temporary"

mv "$temporary" "$backup"
sha256sum "$backup" > "$backup.sha256"
printf '%s\n' "$backup"
