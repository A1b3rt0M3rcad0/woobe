#!/bin/sh
set -e

case "${PROJECTRAI_RUN_MIGRATIONS:-true}" in
  true|TRUE|1|yes|YES)
    echo "Running database migrations..."
    alembic upgrade head
    ;;
  false|FALSE|0|no|NO)
    echo "Skipping database migrations for this runtime."
    ;;
  *)
    echo "Invalid PROJECTRAI_RUN_MIGRATIONS value: ${PROJECTRAI_RUN_MIGRATIONS}" >&2
    exit 2
    ;;
esac

echo "Starting process: $*"
exec "$@"
