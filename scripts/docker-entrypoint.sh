#!/bin/sh
set -e

# Development Docker Compose owns the local Postgres instance, so POSTGRES_*
# is the single credential source. Compose intentionally clears
# PROJECTRAI_DATABASE_URL and provides host/port; derive the application URL
# here with proper URL encoding. External deployments can still provide an
# explicit PROJECTRAI_DATABASE_URL and bypass this derivation entirely.
if [ -z "${PROJECTRAI_DATABASE_URL:-}" ] \
  && [ -n "${POSTGRES_USER:-}" ] \
  && [ -n "${POSTGRES_DB:-}" ]; then
  PROJECTRAI_DATABASE_URL="$(python - <<'PY'
import os
from urllib.parse import quote

user = quote(os.environ["POSTGRES_USER"], safe="")
password = quote(os.environ.get("POSTGRES_PASSWORD", ""), safe="")
database = quote(os.environ["POSTGRES_DB"], safe="")
host = os.environ.get("PROJECTRAI_DATABASE_HOST", "db")
port = os.environ.get("PROJECTRAI_DATABASE_PORT", "5432")

print(f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}")
PY
)"
  export PROJECTRAI_DATABASE_URL
fi

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
