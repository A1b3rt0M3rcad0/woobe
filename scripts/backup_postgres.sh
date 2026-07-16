#!/bin/sh
set -eu

: "${POSTGRES_HOST:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:=projectrai}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${BACKUP_DIR:=/backups}"

umask 077
mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$BACKUP_DIR/projectrai-$timestamp.dump"
temporary="$backup.partial"

export PGPASSWORD="$POSTGRES_PASSWORD"
pg_dump \
  --host "$POSTGRES_HOST" \
  --port "$POSTGRES_PORT" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --format custom \
  --compress 9 \
  --no-owner \
  --no-acl \
  --file "$temporary"

mv "$temporary" "$backup"
sha256sum "$backup" > "$backup.sha256"
printf '%s\n' "$backup"
