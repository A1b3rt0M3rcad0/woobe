#!/bin/sh
set -e

# Docker-managed infrastructure uses credentials from the shared .env contract.
# Connection URLs are derived per container from the target host/port. External
# deployments may still provide explicit PROJECTRAI_*_URL values to bypass this.
if [ -z "${PROJECTRAI_DATABASE_URL:-}" ] \
  && [ -n "${POSTGRES_USER:-}" ] \
  && [ -n "${POSTGRES_DB:-}" ]; then
  PROJECTRAI_DATABASE_URL="$(python - <<'PY'
import os
from urllib.parse import quote

user = quote(os.environ["POSTGRES_USER"], safe="")
password = quote(os.environ.get("POSTGRES_PASSWORD", ""), safe="")
database = quote(os.environ["POSTGRES_DB"], safe="")
host = os.environ.get("PROJECTRAI_DATABASE_HOST", "pgbouncer")
port = os.environ.get("PROJECTRAI_DATABASE_PORT", "6432")

print(f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}")
PY
)"
  export PROJECTRAI_DATABASE_URL
fi

if [ -z "${PROJECTRAI_RABBITMQ_URL:-}" ] \
  && [ -n "${RABBITMQ_USER:-}" ]; then
  PROJECTRAI_RABBITMQ_URL="$(python - <<'PY'
import os
from urllib.parse import quote

user = quote(os.environ["RABBITMQ_USER"], safe="")
password = quote(os.environ.get("RABBITMQ_PASSWORD", ""), safe="")
host = os.environ.get("PROJECTRAI_RABBITMQ_HOST", "rabbitmq")
port = os.environ.get("PROJECTRAI_RABBITMQ_PORT", "5672")

print(f"amqp://{user}:{password}@{host}:{port}/")
PY
)"
  export PROJECTRAI_RABBITMQ_URL
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
