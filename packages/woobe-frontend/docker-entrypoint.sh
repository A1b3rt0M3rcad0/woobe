#!/bin/sh
set -eu

api_url="${WOOBE_PUBLIC_API_URL:-http://localhost:8000}"
chat_embed_url="${WOOBE_PUBLIC_CHAT_EMBED_URL:-http://localhost:8081}"

validate_url() {
  name="$1"
  value="$2"

  case "$value" in
    http://*|https://*) ;;
    *)
      echo "${name} must be an absolute HTTP(S) URL: ${value}" >&2
      exit 1
      ;;
  esac

  case "$value" in
    *\"*|*\\*|*"'"*)
      echo "${name} contains unsupported characters" >&2
      exit 1
      ;;
  esac
}

origin_of() {
  printf '%s\n' "$1" | sed -E 's#^(https?://[^/]+).*$#\1#'
}

validate_url "WOOBE_PUBLIC_API_URL" "$api_url"
validate_url "WOOBE_PUBLIC_CHAT_EMBED_URL" "$chat_embed_url"

api_origin="$(origin_of "$api_url")"
chat_embed_origin="$(origin_of "$chat_embed_url")"

sed \
  -e "s|__API_ORIGIN__|${api_origin}|g" \
  -e "s|__CHAT_EMBED_ORIGIN__|${chat_embed_origin}|g" \
  /etc/nginx/woobe-server.conf.template > /tmp/woobe-server.conf

cat > /tmp/woobe-runtime-config.js <<EOF
window.__WOOBE_CONFIG__ = Object.freeze({
  apiUrl: "${api_url}",
  chatEmbedUrl: "${chat_embed_url}"
});
EOF

exec nginx -c /etc/nginx/woobe-nginx.conf -g 'daemon off;'
