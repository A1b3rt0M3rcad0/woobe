#!/bin/sh
set -eu

: "${PROJECTRAI_BASE_URL:=http://127.0.0.1:8080}"

curl --fail --silent --show-error "$PROJECTRAI_BASE_URL/nginx-health" >/dev/null
curl --fail --silent --show-error "$PROJECTRAI_BASE_URL/live" >/dev/null
curl --fail --silent --show-error "$PROJECTRAI_BASE_URL/ready" >/dev/null
curl --fail --silent --show-error "$PROJECTRAI_BASE_URL/" >/dev/null

if [ -n "${SMOKE_EMAIL:-}" ] && [ -n "${SMOKE_PASSWORD:-}" ]; then
  response="$(curl --fail --silent --show-error \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$SMOKE_EMAIL\",\"password\":\"$SMOKE_PASSWORD\"}" \
    "$PROJECTRAI_BASE_URL/identity/auth/login")"
  token="$(printf '%s' "$response" | python -c \
    'import json,sys; print(json.load(sys.stdin)["data"]["access_token"])')"
  curl --fail --silent --show-error \
    -H "Authorization: Bearer $token" \
    "$PROJECTRAI_BASE_URL/identity/users/me" >/dev/null

  if [ -n "${SMOKE_PROJECT_ID:-}" ]; then
    curl --fail --silent --show-error \
      -H "Authorization: Bearer $token" \
      "$PROJECTRAI_BASE_URL/core/projects/$SMOKE_PROJECT_ID/overview" >/dev/null
  fi
fi

printf '%s\n' "Production smoke checks passed"
