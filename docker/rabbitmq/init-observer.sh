#!/bin/sh
set -eu

api_base="${RABBITMQ_MANAGEMENT_URL%/}/api"
auth="${RABBITMQ_USER}:${RABBITMQ_PASSWORD}"
vhost_path="%2F"
trace_pattern="${RABBITMQ_OBSERVER_TRACE_PATTERN:-publish.${RABBITMQ_EXCHANGE}}"

json_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

require_positive_integer() {
  name="$1"
  value="$2"
  case "$value" in
    ''|*[!0-9]*)
      echo "$name must be a positive integer" >&2
      exit 1
      ;;
  esac
  if [ "$value" -le 0 ]; then
    echo "$name must be greater than zero" >&2
    exit 1
  fi
}

request() {
  method="$1"
  url="$2"
  payload="$3"
  curl \
    --fail \
    --silent \
    --show-error \
    --retry 20 \
    --retry-delay 1 \
    --retry-connrefused \
    --user "$auth" \
    --header 'content-type: application/json' \
    --request "$method" \
    --data "$payload" \
    "$url" \
    >/dev/null
}

require_positive_integer \
  RABBITMQ_OBSERVER_MESSAGE_TTL_MS \
  "$RABBITMQ_OBSERVER_MESSAGE_TTL_MS"
require_positive_integer \
  RABBITMQ_OBSERVER_MAX_MESSAGES \
  "$RABBITMQ_OBSERVER_MAX_MESSAGES"
require_positive_integer \
  RABBITMQ_OBSERVER_MAX_PAYLOAD_BYTES \
  "$RABBITMQ_OBSERVER_MAX_PAYLOAD_BYTES"

exchange_json=$(printf \
  '{"type":"topic","durable":true,"auto_delete":false,"internal":false,"arguments":{}}')
queue_json=$(printf \
  '{"durable":true,"auto_delete":false,"arguments":{"x-queue-type":"classic","x-message-ttl":%s,"x-max-length":%s,"x-overflow":"drop-head"}}' \
  "$RABBITMQ_OBSERVER_MESSAGE_TTL_MS" \
  "$RABBITMQ_OBSERVER_MAX_MESSAGES")
binding_json='{"routing_key":"#","arguments":{}}'
trace_json=$(printf \
  '{"format":"json","pattern":"%s","max_payload_bytes":%s,"tracer_connection_username":"%s","tracer_connection_password":"%s"}' \
  "$(json_escape "$trace_pattern")" \
  "$RABBITMQ_OBSERVER_MAX_PAYLOAD_BYTES" \
  "$(json_escape "$RABBITMQ_USER")" \
  "$(json_escape "$RABBITMQ_PASSWORD")")

request \
  PUT \
  "$api_base/exchanges/$vhost_path/$RABBITMQ_EXCHANGE" \
  "$exchange_json"
request \
  PUT \
  "$api_base/queues/$vhost_path/$RABBITMQ_OBSERVER_QUEUE" \
  "$queue_json"
request \
  POST \
  "$api_base/bindings/$vhost_path/e/$RABBITMQ_EXCHANGE/q/$RABBITMQ_OBSERVER_QUEUE" \
  "$binding_json"
request \
  PUT \
  "$api_base/traces/$vhost_path/$RABBITMQ_OBSERVER_TRACE_NAME" \
  "$trace_json"

echo "RabbitMQ observer ready"
echo "Management UI: ${RABBITMQ_MANAGEMENT_URL}"
echo "Mirror queue: ${RABBITMQ_OBSERVER_QUEUE}"
echo "Trace: ${RABBITMQ_OBSERVER_TRACE_NAME} (${trace_pattern})"
