#!/usr/bin/env bash
set -euo pipefail

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

# Signal the host-level validation lock holder to release the Docker daemon for the
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
