#!/bin/sh
set -eu

: "${RESTORE_FILE:?RESTORE_FILE is required}"
: "${RESTORE_CONFIRM:?Set RESTORE_CONFIRM=restore-projectrai to continue}"
: "${PROJECTRAI_POSTGRES_URL:?PROJECTRAI_POSTGRES_URL is required}"
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

if [ "$RESTORE_CLEAN" = "true" ]; then
  pg_restore \
    --dbname "$PROJECTRAI_POSTGRES_URL" \
    --clean \
    --if-exists \
    --no-owner \
    --no-acl \
    --exit-on-error \
    "$RESTORE_FILE"
else
  pg_restore \
    --dbname "$PROJECTRAI_POSTGRES_URL" \
    --no-owner \
    --no-acl \
    --exit-on-error \
    "$RESTORE_FILE"
fi
