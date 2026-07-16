#!/bin/sh
set -eu

: "${RESTORE_FILE:?RESTORE_FILE is required}"
: "${RESTORE_CONFIRM:?Set RESTORE_CONFIRM=restore-projectrai to continue}"
: "${POSTGRES_HOST:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:=projectrai}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${RESTORE_CLEAN:=true}"

if [ "$RESTORE_CONFIRM" != "restore-projectrai" ]; then
  echo "Refusing restore: RESTORE_CONFIRM must equal restore-projectrai" >&2
  exit 2
fi
if [ "$RESTORE_CLEAN" != "true" ] && [ "$RESTORE_CLEAN" != "false" ]; then
  echo "Refusing restore: RESTORE_CLEAN must be true or false" >&2
  exit 2
fi
if [ ! -f "$RESTORE_FILE" ]; then
  echo "Restore file does not exist: $RESTORE_FILE" >&2
  exit 2
fi
if [ -f "$RESTORE_FILE.sha256" ]; then
  sha256sum -c "$RESTORE_FILE.sha256"
fi

export PGPASSWORD="$POSTGRES_PASSWORD"
if [ "$RESTORE_CLEAN" = "true" ]; then
  pg_restore \
    --host "$POSTGRES_HOST" \
    --port "$POSTGRES_PORT" \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --clean \
    --if-exists \
    --no-owner \
    --no-acl \
    --exit-on-error \
    "$RESTORE_FILE"
else
  pg_restore \
    --host "$POSTGRES_HOST" \
    --port "$POSTGRES_PORT" \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --no-owner \
    --no-acl \
    --exit-on-error \
    "$RESTORE_FILE"
fi
