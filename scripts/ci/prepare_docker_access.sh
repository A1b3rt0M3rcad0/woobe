#!/usr/bin/env bash
set -euo pipefail

runner_temp="${RUNNER_TEMP:-/tmp}"
workspace="${GITHUB_WORKSPACE:-$(pwd)}"
run_id="${GITHUB_RUN_ID:-local}"
attempt="${GITHUB_RUN_ATTEMPT:-1}"
job_name="${GITHUB_JOB:-job}"

lock_file="/tmp/woobe-docker-validation.lock"
lock_acquired_file="$runner_temp/woobe-docker-lock-${run_id}-${attempt}-${job_name}.acquired"
lock_release_file="$runner_temp/woobe-docker-lock-${run_id}-${attempt}-${job_name}.release"
lock_pid_file="$runner_temp/woobe-docker-lock-${run_id}-${attempt}-${job_name}.pid"
lock_log="$runner_temp/woobe-docker-lock-${run_id}-${attempt}-${job_name}.log"

rm -f "$lock_acquired_file" "$lock_release_file" "$lock_pid_file" "$lock_log"

# All self-hosted runners currently share the same physical Docker host. Serialize
# Docker-heavy validation on the host itself instead of using GitHub concurrency
# groups, which keep only one pending job and can cancel unrelated required checks.
nohup bash -c '
  set -eu
  lock_file="$1"
  acquired="$2"
  release="$3"
  exec 9>"$lock_file"
  flock -x 9
  : > "$acquired"
  elapsed=0
  while [ ! -e "$release" ] && [ "$elapsed" -lt 3600 ]; do
    sleep 1
    elapsed=$((elapsed + 1))
  done
' _ "$lock_file" "$lock_acquired_file" "$lock_release_file" >"$lock_log" 2>&1 &
echo $! > "$lock_pid_file"

for _ in $(seq 1 2400); do
  if [[ -f "$lock_acquired_file" ]]; then
    break
  fi
  lock_pid="$(cat "$lock_pid_file" 2>/dev/null || true)"
  if [[ -n "$lock_pid" ]] && ! kill -0 "$lock_pid" 2>/dev/null; then
    echo "::error::Docker validation lock process exited before acquiring the host lock."
    cat "$lock_log" 2>/dev/null || true
    exit 1
  fi
  sleep 1
done

if [[ ! -f "$lock_acquired_file" ]]; then
  echo "::error::Timed out waiting for the shared Docker validation lock."
  cat "$lock_log" 2>/dev/null || true
  exit 1
fi

if [[ -n "${GITHUB_ENV:-}" ]]; then
  {
    echo "WOOBE_DOCKER_LOCK_ACQUIRED_FILE=$lock_acquired_file"
    echo "WOOBE_DOCKER_LOCK_RELEASE_FILE=$lock_release_file"
    echo "WOOBE_DOCKER_LOCK_PID_FILE=$lock_pid_file"
    echo "WOOBE_DOCKER_LOCK_LOG=$lock_log"
  } >> "$GITHUB_ENV"
fi

echo "Acquired shared Docker validation lock on runner ${RUNNER_NAME:-unknown}."

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

proxy_socket="$runner_temp/woobe-docker-${run_id}-${attempt}-${job_name}.sock"
proxy_pid_file="$runner_temp/woobe-docker-${run_id}-${attempt}-${job_name}.pid"
proxy_log="$runner_temp/woobe-docker-${run_id}-${attempt}-${job_name}.log"

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
