#!/usr/bin/env bash
set -euo pipefail

if docker info >/dev/null 2>&1; then
  echo "Docker daemon is directly accessible on runner ${RUNNER_NAME:-unknown}."
  exit 0
fi

user="$(id -un)"
if ! command -v sg >/dev/null 2>&1; then
  echo "::error::Docker is not directly accessible and 'sg' is unavailable."
  exit 1
fi

if ! id -nG "$user" | tr ' ' '\n' | grep -Fxq docker; then
  echo "::error::Docker is not directly accessible and user '$user' is not configured in the docker group."
  echo "Configured groups: $(id -nG "$user")"
  exit 1
fi

runner_temp="${RUNNER_TEMP:-/tmp}"
workspace="${GITHUB_WORKSPACE:-$(pwd)}"
run_id="${GITHUB_RUN_ID:-local}"
attempt="${GITHUB_RUN_ATTEMPT:-1}"
proxy_socket="$runner_temp/woobe-docker-${run_id}-${attempt}.sock"
proxy_pid_file="$runner_temp/woobe-docker-${run_id}-${attempt}.pid"
proxy_log="$runner_temp/woobe-docker-${run_id}-${attempt}.log"

rm -f "$proxy_socket" "$proxy_pid_file" "$proxy_log"

printf -v proxy_command \
  'nohup python3 %q --listen %q --upstream /var/run/docker.sock >%q 2>&1 & echo $! >%q' \
  "$workspace/scripts/ci/docker_socket_proxy.py" \
  "$proxy_socket" \
  "$proxy_log" \
  "$proxy_pid_file"

sg docker -c "$proxy_command"

for _ in $(seq 1 50); do
  if [[ -S "$proxy_socket" ]]; then
    break
  fi
  sleep 0.1
done

if [[ ! -S "$proxy_socket" ]]; then
  echo "::error::Docker compatibility proxy did not create its socket."
  cat "$proxy_log" 2>/dev/null || true
  exit 1
fi

export DOCKER_HOST="unix://$proxy_socket"
if ! docker info >/dev/null 2>&1; then
  echo "::error::Docker compatibility proxy started, but the daemon is still unreachable."
  cat "$proxy_log" 2>/dev/null || true
  if [[ -f "$proxy_pid_file" ]]; then
    kill "$(cat "$proxy_pid_file")" 2>/dev/null || true
  fi
  exit 1
fi

if [[ -n "${GITHUB_ENV:-}" ]]; then
  {
    echo "DOCKER_HOST=$DOCKER_HOST"
    echo "WOOBE_DOCKER_PROXY_SOCKET=$proxy_socket"
    echo "WOOBE_DOCKER_PROXY_PID_FILE=$proxy_pid_file"
    echo "WOOBE_DOCKER_PROXY_LOG=$proxy_log"
  } >> "$GITHUB_ENV"
fi

echo "Docker access recovered through user-owned proxy socket $proxy_socket."
