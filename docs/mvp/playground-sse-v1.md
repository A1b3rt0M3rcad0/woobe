# Playground SSE protocol v1

The playground streaming endpoint is `POST /runtime/ask/stream` with media type `text/event-stream`.

Every event is encoded as one JSON object in an SSE `data:` field and contains:

- `type`: event type;
- `protocol_version`: currently `1`;
- `request_id`: server-generated request identifier;
- `occurred_at`: UTC timestamp.

## Event sequence

A successful execution emits an early `meta` event after trace, session, and user-message persistence. It can then emit `sources`, progressive `token` events, tool events, `fallback`, and periodic `heartbeat` events. A `usage` event precedes the terminal `done` event.

Tool execution uses two events:

- `tool_call_started`: tool name, call identifier, input, and start time;
- `tool_call_completed`: output, status, duration, and error when applicable.

Exactly one terminal event is emitted:

- `done`: persisted response and execution metadata;
- `error`: safe error code and correlation identifiers;
- `cancelled`: execution cancelled because the client disconnected or the stream closed.

Consumers must ignore unknown event types, tolerate arbitrary network chunk boundaries, process a final unterminated buffer, and never assume that `Response.body` is present.

## Cancellation

Closing the browser request cancels the provider task. When a trace has already been created, the runtime writes an `agent.execution.cancelled.v1` outbox event so observability can project the terminal cancelled state.

## Security

Error events do not contain provider responses, credentials, request headers, or raw exception text. Administrative playground calls may use a draft snapshot override; production API-key calls must not use playground overrides.
