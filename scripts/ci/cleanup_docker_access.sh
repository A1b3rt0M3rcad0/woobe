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
