# Runtime streaming and reattach

## Lazy execution

Creating a Chat does not perform network I/O:

```python
chat = agent.chat(input="Olá")
```

The first Runtime API request starts only when the async generator returned by `events()` begins iteration:

```python
async for event in chat.events():
    ...
```

This prevents a Run from starting merely because an object was constructed.

## Initial request

The SDK maps the Python call to the public Runtime API:

```text
agent.chat(input="Olá", session_id=..., external_context=...)
              |
              v
POST /v1/run/stream
{
  "message": "Olá",
  "session_id": "...",
  "external_context": {
    "customer_id": "customer-123"
  }
}
```

Agent and Network Runtime Keys use the same public Runtime API surface. The server resolves the target from the Runtime Key binding.

External Context is an input to Run Acceptance. When supplied, the SDK sends it only on the initial create-and-observe request. Reattach requests identify the existing Run by `run_id` and do not resend `external_context`.

## Canonical semantic envelope

Runtime Protocol v2 makes every semantic event self-contained:

```json
{
  "protocol_version": 2,
  "event_id": "019...",
  "run_id": "019...",
  "session_id": "019...",
  "run_kind": "AGENT",
  "sequence": 42,
  "type": "token",
  "occurred_at": "2026-09-16T20:30:00Z",
  "payload": {
    "content": "Olá"
  }
}
```

The SDK validates this envelope directly. It does not infer canonical identity from `execution_id`, `network_session_id`, nested `data`, SSE cursor values or payload fields.

For Network execution, `run_id` is the canonical Network execution identity, `session_id` is the canonical Network Session identity and `run_kind` is `NETWORK`.

Once the first semantic event is accepted, Run and Session identity are immutable for that `Chat`. `run_kind` must also match the connected target.

## Transport/control frames

Heartbeat, realtime-degradation signals and failures before Run acceptance are transport/control frames. They use protocol v2 but do not invent `run_id`, `session_id`, `event_id` or semantic `sequence`.

These frames are handled internally. `Chat.events()` yields only semantic `WoobeEvent` objects.

A pre-Acceptance `error` control frame becomes a request error. Heartbeats and non-fatal control signals do not enter the application's semantic event stream.

## Sequence semantics

`sequence` is the logical ordering contract for semantic events. The SSE `id:` field is not used to manufacture a missing sequence; if present, it must agree with the envelope sequence.

For incremental events:

- sequence `<=` the last accepted sequence is stale/duplicate and is ignored;
- sequence `> last + 1` is a gap and triggers recovery;
- contiguous sequence advances the local high watermark.

`run.state` is replacement state. It may advance directly to the high watermark represented by its snapshot. A durable-only `run.state` with `realtime_available=false` is accepted without rewinding the local realtime sequence.

## Reattach

After `run_id` is known, a broken SSE connection becomes observation recovery:

```text
stream interrupted
      |
      v
GET /v1/runs/{run_id}/stream
      |
      v
run.state @ high watermark
      |
      v
live events after the snapshot
```

The SDK never starts another Agent Run to repair transport after canonical Run identity is known.

If the SDK knows a Session but lost the Run pointer, it first asks:

```text
GET /v1/sessions/{session_id}/active-run
```

The response is expected to expose canonical `run_id`; the SDK no longer falls back to Network-specific identity aliases.

## Initial-create failure window

The dangerous window is a connection failure after the server may have accepted work but before the client has learned canonical identity.

For Agent runtime, the SDK fails closed instead of automatically POSTing the same logical request again when the Run cannot be recovered safely.

For Network runtime, the SDK creates one idempotency key per Chat and reuses it if the initial create-and-stream request must be retried before a Run ID is known.

## Terminal events

Terminal semantic events or terminal `run.state` end `events()` normally. Agent or Network execution failure remains a Runtime semantic outcome and is distinct from a transport exception.

Terminal statuses include `completed`, `failed`, `cancelled`, `timed_out` and `uncertain`.

The core rule is: the Run belongs to the Runtime; the connection belongs to the observer.
