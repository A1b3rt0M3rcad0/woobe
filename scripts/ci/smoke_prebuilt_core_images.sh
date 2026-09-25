#!/usr/bin/env bash
set -euo pipefail

: "${WOOBE_API_IMAGE:?WOOBE_API_IMAGE is required}"
: "${WOOBE_WORKERS_IMAGE:?WOOBE_WORKERS_IMAGE is required}"
: "${WOOBE_FRONTEND_IMAGE:?WOOBE_FRONTEND_IMAGE is required}"
: "${WOOBE_EMBED_IMAGE:?WOOBE_EMBED_IMAGE is required}"

compose=(
  docker compose
  -f compose.yaml
  -f docker/ci/compose.release-images.yml
)

"${compose[@]}" config --quiet
"${compose[@]}" up -d --no-build db rabbitmq redis mongodb
"${compose[@]}" run --rm migrate

if ! "${compose[@]}" up -d --no-build api workers web chat-embed; then
  "${compose[@]}" ps --all || true
  "${compose[@]}" logs --no-color api workers mongodb rabbitmq redis || true
  exit 1
fi

for _ in $(seq 1 60); do
  if sh scripts/smoke_production.sh \
    && "${compose[@]}" exec -T workers sh -c 'python -m woobe_workers.runtime.health check "${WOOBE_WORKER_HEALTH_FILE:-/tmp/woobe/worker-health.json}" "${WOOBE_WORKER_HEALTH_MAX_AGE_SECONDS:-45}"'; then
    printf '%s\n' "Prebuilt Woobe image smoke checks passed"
    exit 0
  fi
  sleep 2
done

"${compose[@]}" ps --all || true
"${compose[@]}" logs --no-color || true
exit 1
