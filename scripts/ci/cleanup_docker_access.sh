#!/usr/bin/env bash
set -euo pipefail

# The hosted VM is ephemeral but provides limited SSD space. Discard unused
# images and build cache between CI phases; never clean running containers.
if [[ "${RUNNER_ENVIRONMENT:-}" == "github-hosted" ]]; then
  docker builder prune --all --force >/dev/null 2>&1 || true
  docker image prune --all --force >/dev/null 2>&1 || true
  exit 0
fi

if [[ -n "${WOOBE_DOCKER_PROXY_PID_FILE:-}" && -f "$WOOBE_DOCKER_PROXY_PID_FILE" ]]; then
  pid="$(cat "$WOOBE_DOCKER_PROXY_PID_FILE")"
  if [[ -n "$pid" ]]; then
    kill "$pid" 2>/dev/null || true
  fi
fi

if [[ -n "${WOOBE_DOCKER_PROXY_SOCKET:-}" ]]; then
  rm -f "$WOOBE_DOCKER_PROXY_SOCKET"
fi
if [[ -n "${WOOBE_DOCKER_PROXY_PID_FILE:-}" ]]; then
  rm -f "$WOOBE_DOCKER_PROXY_PID_FILE"
fi

# Legacy shared-host fallback: signal the lock holder to release Docker for the
# next heavy CI job. Killing the holder is a final safety net for cancelled jobs.
if [[ -n "${WOOBE_DOCKER_LOCK_RELEASE_FILE:-}" ]]; then
  : > "$WOOBE_DOCKER_LOCK_RELEASE_FILE"
fi

if [[ -n "${WOOBE_DOCKER_LOCK_PID_FILE:-}" && -f "$WOOBE_DOCKER_LOCK_PID_FILE" ]]; then
  lock_pid="$(cat "$WOOBE_DOCKER_LOCK_PID_FILE")"
  if [[ -n "$lock_pid" ]]; then
    for _ in $(seq 1 20); do
      if ! kill -0 "$lock_pid" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    kill "$lock_pid" 2>/dev/null || true
  fi
fi

rm -f \
  "${WOOBE_DOCKER_LOCK_ACQUIRED_FILE:-}" \
  "${WOOBE_DOCKER_LOCK_RELEASE_FILE:-}" \
  "${WOOBE_DOCKER_LOCK_PID_FILE:-}"
