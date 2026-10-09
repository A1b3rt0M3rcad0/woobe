#!/usr/bin/env bash
set -euo pipefail

# Registry credentials and Buildx state belong to this job, never the runner's
# persistent ~/.docker. Preserve access to user-installed CLI plugins only.
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
umask 077
original_config="${DOCKER_CONFIG:-$HOME/.docker}"
release_config="$(mktemp -d "$RUNNER_TEMP/woobe-release-docker.XXXXXXXX")"
trap 'rm -rf -- "$release_config"' EXIT
if [[ -d "$original_config/cli-plugins" ]]; then
  cp -RL "$original_config/cli-plugins" "$release_config/cli-plugins"
fi
printf 'DOCKER_CONFIG=%s\nWOOBE_RELEASE_DOCKER_CONFIG=%s\n' \
  "$release_config" "$release_config" >> "$GITHUB_ENV"
trap - EXIT
