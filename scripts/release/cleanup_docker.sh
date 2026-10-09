#!/usr/bin/env bash
set -euo pipefail

# Run before releasing the shared daemon. Docker action post hooks are disabled
# so they cannot touch a builder after another CI job acquires the host lock.
cleanup() {
  local result=$?
  if [[ -n "${WOOBE_RELEASE_DOCKER_CONFIG:-}" ]]; then
    if [[ "$WOOBE_RELEASE_DOCKER_CONFIG" == "${RUNNER_TEMP:?}"/woobe-release-docker.* ]]; then
      rm -rf -- "$WOOBE_RELEASE_DOCKER_CONFIG"
    else
      echo "::error::Refusing to remove an unrelated Docker configuration."
      result=1
    fi
  fi
  bash scripts/ci/cleanup_docker_access.sh || result=1
  exit "$result"
}
trap cleanup EXIT
if [[ -n "${WOOBE_RELEASE_BUILDER:-}" ]]; then
  docker buildx rm "$WOOBE_RELEASE_BUILDER"
fi
if [[ -n "${WOOBE_RELEASE_DOCKER_CONFIG:-}" ]]; then
  docker logout ghcr.io
fi
