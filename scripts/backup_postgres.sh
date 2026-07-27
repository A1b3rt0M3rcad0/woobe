#!/bin/sh
set -eu

: "${PROJECTRAI_POSTGRES_URL:?PROJECTRAI_POSTGRES_URL is required}"
: "${BACKUP_DIR:=/backups}"

umask 077
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$BACKUP_DIR/projectrai-$timestamp.dump"
temporary="$backup.partial"

pg_dump \
  --dbname "$PROJECTRAI_POSTGRES_URL" \
  --format custom \
  --compress 9 \
  --no-owner \
  --no-acl \
  --file "$temporary"

mv "$temporary" "$backup"
sha256sum "$backup" > "$backup.sha256"
printf '%s\n' "$backup"
