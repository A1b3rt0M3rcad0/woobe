#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ARTIFACT_DIR="$ROOT_DIR/.test-artifacts"
TEST_ENV="$ROOT_DIR/deploy/test/test.env"

compose() {
  docker compose \
    --env-file "$TEST_ENV" \
    -p woobe-test \
    -f "$ROOT_DIR/compose.yaml" \
    -f "$ROOT_DIR/deploy/dev/compose.yml" \
    -f "$ROOT_DIR/deploy/test/compose.yml" \
    "$@"
}

prepare_artifacts() {
  mkdir -p "$ARTIFACT_DIR"
}

cleanup() {
  compose down -v --remove-orphans >/dev/null 2>&1 || true
}

run_backend() {
  compose build backend-tests fake-llm
  compose run --rm backend-tests
}

run_frontend() {
  compose build frontend-tests
  compose run --rm frontend-tests
}

run_mocked_browser() {
  compose build web-preview browser-mocked
  compose up -d web-preview
  compose run --rm browser-mocked
}

run_fullstack_e2e() {
  cleanup
  compose build fake-llm api workers web chat-embed browser-e2e
  compose up -d db rabbitmq pgbouncer redis minio
  compose up --no-deps minio-init
  compose up -d fake-llm
  compose run --rm migrate
  compose up -d api workers web chat-embed
  compose run --rm browser-e2e
}

usage() {
  cat <<'EOF'
Usage: sh scripts/test.sh [backend|frontend|mocked|e2e|all|down]
EOF
}

command=${1:-all}
prepare_artifacts

case "$command" in
  backend)
    trap cleanup EXIT INT TERM
    run_backend
    ;;
  frontend)
    trap cleanup EXIT INT TERM
    run_frontend
    ;;
  mocked)
    trap cleanup EXIT INT TERM
    run_mocked_browser
    ;;
  e2e)
    trap cleanup EXIT INT TERM
    run_fullstack_e2e
    ;;
  all)
    trap cleanup EXIT INT TERM
    cleanup
    run_backend
    run_frontend
    run_mocked_browser
    run_fullstack_e2e
    ;;
  down)
    cleanup
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
