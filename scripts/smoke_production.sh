#!/bin/sh
set -eu

: "${WOOBE_WEB_BASE_URL:=http://127.0.0.1:8080}"
: "${WOOBE_API_BASE_URL:=http://127.0.0.1:8000}"
: "${WOOBE_CHAT_EMBED_BASE_URL:=http://127.0.0.1:8081}"

curl --fail --silent --show-error "$WOOBE_WEB_BASE_URL/nginx-health" >/dev/null
curl --fail --silent --show-error "$WOOBE_WEB_BASE_URL/" >/dev/null
curl --fail --silent --show-error "$WOOBE_API_BASE_URL/live" >/dev/null
curl --fail --silent --show-error "$WOOBE_API_BASE_URL/ready" >/dev/null
curl --fail --silent --show-error "$WOOBE_CHAT_EMBED_BASE_URL/chat/v1/health" >/dev/null

if [ -n "${SMOKE_EMAIL:-}" ] && [ -n "${SMOKE_PASSWORD:-}" ]; then
  cookie_jar="$(mktemp)"
  trap 'rm -f "$cookie_jar"' EXIT
  curl --fail --silent --show-error \
    -c "$cookie_jar" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}" \
    "$WOOBE_API_BASE_URL/identity/auth/login" >/dev/null
  curl --fail --silent --show-error \
    -b "$cookie_jar" \
    "$WOOBE_API_BASE_URL/identity/users/me" >/dev/null

  if [ -n "${SMOKE_PROJECT_ID:-}" ]; then
    curl --fail --silent --show-error \
      -b "$cookie_jar" \
      "$WOOBE_API_BASE_URL/core/projects/$SMOKE_PROJECT_ID/overview" >/dev/null
  fi
fi

printf '%s\n' "Woobe production smoke checks passed"
