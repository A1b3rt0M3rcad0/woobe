# Runtime streaming and reattach protocol

Woobe treats streaming as an observation interface over an existing Run. The HTTP/SSE connection does not own the Agent Run or Network Run lifecycle.

The runtime invariant is:

```text
Acceptance (durable PostgreSQL)
        ↓
Execution (runtime + Redis hot state/events)
        ↓
Finalization (durable PostgreSQL)
```

SSE observes this lifecycle. Closing a tab, refreshing the page, losing the network, or disconnecting an SSE client only removes that observer. It must not cancel, restart, or duplicate the Run.

Every accepted Run belongs to a Session. This includes stateless Agent execution: when the caller does not provide a Session, the runtime creates an isolated Session for identity and correlation. Stateless still means that previous Session history is not implicitly loaded into later execution context; it does not mean that the Run is sessionless.

## External Context lifecycle

External Context is resolved during Acceptance before execution begins. Lifecycle is declared per field:

- `scope: session` is write-once per field for the Session;
- `scope: run` is resolved independently for each Run;
- an omitted `scope` means `run` for backward compatibility.

The durable Session snapshot stores only Session-scoped fields that have already been initialized. The Run snapshot stores only the current Run-scoped values. The effective context consumed by the runtime is:

```text
Session.external_context_snapshot
+ current Run external_context_snapshot
= effective External Context
```

A Session field may be initialized by an explicit caller value or by its contract default. Once fixed, public callers must omit that field on later Runs. Re-sending an already fixed Session field is rejected with `EXTERNAL_CONTEXT_SESSION_FIELD_ALREADY_SET`; a persisted Session value that no longer satisfies the active contract is rejected with `EXTERNAL_CONTEXT_SESSION_CONTRACT_CONFLICT` and requires a new Session.

Session snapshots are reconciled against the active contract on every Run. Newly introduced Session fields may still be initialized later when they have never been set, but removed fields, lifecycle changes, or values that no longer validate make the existing Session incompatible.

Networks use the same lifecycle semantics. The Network Session owns Session-scoped values, Network executions own Run-scoped values, and child Agents receive a projection of the already resolved effective context. Internal Network-to-Agent propagation may replay an identical fixed Session value; a conflicting value is still rejected.

Reattach observes an already accepted Run and never re-resolves or resends External Context.

## Runtime stream protocol v2

Every semantic Runtime event emitted after Acceptance is self-contained:

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

`run_kind` is `AGENT` or `NETWORK`. For Network execution, canonical `run_id` is the Network execution identity and canonical `session_id` is the Network Session identity. Legacy/domain names such as `execution_id` and `network_session_id` may still exist behind internal adapters, but they are not a second public stream identity model.

Transport/control frames are intentionally separate from semantic events. Heartbeats, realtime-degradation notices and failures that occur before a Run has been accepted do not invent `run_id`, `session_id` or a semantic sequence.

The public protocol does not depend on a preceding `meta` event to discover identity. Every semantic event carries the Run and Session identity required to correlate it independently.

## Public observation model

A client attaches to an existing Run and receives:

```text
current projected state
        ↓
live tail after that state
```

The first frame is `run.state`. It has replacement semantics: the consumer should reconcile its local view to the complete state carried by the frame rather than visually replaying every event that occurred while it was disconnected.

Example:

```text
client last saw sequence 125
runtime advanced through 126..131
client reconnects
→ run.state @131
→ event 132
→ event 133
```

The server folds 126..131 into the projection before sending the initial state. The browser does not need to animate those events individually.

## High-watermark rule

Attach must avoid a gap between state reconstruction and the live stream:

```text
1. load saved projection P
2. capture the current event high-watermark H
3. read and fold P.sequence < events <= H
4. emit run.state @H
5. follow events > H
```

Events published while step 3 is running remain after `H` and are delivered by the live tail. If the retained stream can no longer bridge the projection because Redis trimming removed required events, Woobe reports a degraded state instead of inventing continuity.

## Event identity and ordering

Woobe distinguishes:

- `RuntimeEvent.sequence`: monotonic logical ordering within one Run;
- Redis Stream ID/cursor: infrastructure cursor used to continue reading the stream.

The domain and clients must not use the Redis Stream ID as the semantic ordering contract.

For the Agent initial fast path, semantic identity and sequence are assigned before the event is delivered locally. Hot persistence must preserve that exact identity/order; it must not create a second sequence for the same public event. This keeps first-token latency independent from Redis while allowing reattach to continue from the exact next sequence.

The durable Run Event Journal is a different internal stream and keeps its own journal sequence. Journal events and public Runtime events do not have 1:1 cardinality, so their sequences must not be artificially unified.

## Redis responsibilities

Redis is hot operational state, not the durable source of truth. It stores:

- in-flight execution state;
- ordered runtime events;
- runtime projection checkpoints;
- cancellation flags and execution coordination where applicable;
- short-lived data required for reattach;
- a best-effort `reattach_count` operational counter while the hot Run exists.

Projection checkpoints may be batched for high-frequency token events. Structural transitions are checkpointed eagerly. The stream remains the catch-up source between the saved projection and the captured high-watermark.

PostgreSQL remains authoritative for accepted Runs, final results, semantic history, messages, versions, usage, traces, and final statuses.

## Agent endpoints

The existing convenience endpoint can create and immediately observe an Agent Run:

```text
POST /runtime/ask/stream
```

After the canonical Run identity is known, transport retries use:

```text
GET /runtime/runs/{run_id}/stream
```

A Control Plane client that retained only a Session can discover its current direct Agent Run through:

```text
GET /runtime/runs/active?session_id={session_id}
```

Explicit cancellation is independent from stream disconnect:

```text
POST /runtime/runs/{run_id}/cancel
```

The Agent client never automatically submits a second POST after a Run ID is known. A transport interruption becomes a reattach operation. The Playground stores the selected Session and active Run identity as ergonomic reload pointers, then validates/reconstructs state from the backend. Server state remains canonical.

## Network endpoints

The existing Network streaming POST remains a convenience create-and-observe entrypoint. The canonical Network Run can be observed independently through:

```text
GET /network/executions/{execution_id}/stream
```

An active execution can be discovered either from a known Network Session or, for Control Plane reload recovery, by Network/environment:

```text
GET /network/executions/active?network_session_id={session_id}
GET /network/executions/active?network_id={network_id}&environment={environment}
```

The HTTP route can retain `execution_id` for domain/API compatibility, but the Runtime stream emitted by it uses canonical `run_id == execution_id` and `session_id == network_session_id`.

Once the Network execution ID is known, the web client switches transport retries to the GET endpoint. Before the ID is available, the existing Network idempotency key is reused so retries resolve to the same logical Network Run.

Network execution is worker-owned; observer disconnects do not own worker cancellation.

## Public Runtime API reload/reattach

Reload and reconnect semantics are part of the API contract, not only the Woobe UI.

The initial Runtime Key request remains:

```text
POST /v1/run/stream
Authorization: Bearer $WOOBE_RUNTIME_KEY
```

As soon as the client receives the canonical `run_id` and `session_id` in any semantic event, it can retain them. Reattach is then:

```text
GET /v1/runs/{run_id}/stream
Authorization: Bearer $WOOBE_RUNTIME_KEY
```

A caller that retained the Session ID but lost the Run ID may first resolve the active Run:

```text
GET /v1/sessions/{session_id}/active-run
Authorization: Bearer $WOOBE_RUNTIME_KEY
```

Then it attaches to the returned `run_id` through `/v1/runs/{run_id}/stream`.

Stateless Agent execution follows the same identity rule: it has an isolated Session even when the caller did not supply one. That Session is useful for correlation and active-Run recovery, but it must not be interpreted as permission to load previous conversational history into a later stateless execution.

Runtime Key isolation is enforced again on reattach. A Runtime Key cannot attach a Run belonging to another Project, target Agent/Network, or environment. Reattach GETs require the `stream` interface and normal Runtime Key scope/rate-limit checks, but they do not consume an execution-concurrency permit because they observe an existing Run rather than start work.

Observation remains valid even if new-run admission is later disabled for the environment. Disabling the runtime prevents new executions; it does not hide or cancel an already accepted Run.

## Browser reload behavior

### Agent Playground

The Playground persists the selected Session ID and active Run ID locally as pointers. After F5 it:

1. reloads persisted Session history when the Agent/session policy allows continuity;
2. resolves the active Run from the stored Run ID or `GET /runtime/runs/active`;
3. attaches to the same Run;
4. receives `run.state` with the output already produced;
5. continues with the live tail.

For stateless Agents, the isolated Session remains a correlation boundary, but its prior history is not implicitly fed into subsequent Runs.

### Network workspace

The Network workspace does not require a local Run object to survive F5. It asks the backend for an active execution for the current Network/environment. If one exists, it selects the corresponding Network Session and reattaches to that execution.

### ChatSurface / Embed

A ChatSurface message request remains `accepted`/`streaming` while its underlying Agent/Network Run is non-terminal. Ending an iframe/SSE observer no longer marks the message request failed or completed.

After iframe reload the embed performs:

```text
GET /v1/chat/sessions/{session_id}/active-run
GET /v1/chat/sessions/{session_id}/active-run/stream
```

using the existing ChatSurface Session token and host-origin binding. The same `current state -> live tail` protocol is used. Once durable completion is observed, normal message history becomes authoritative again.

## SSE frames

### Semantic event

A semantic event uses protocol v2 and always carries:

- `event_id`;
- `run_id`;
- `session_id`;
- `run_kind`;
- `sequence`;
- `type`;
- `occurred_at`;
- `payload`.

Consumers should read domain-specific fields from `payload`. They should not infer Runtime identity from payload aliases.

### `run.state`

`run.state` is the initial replacement event for an attach/reattach operation. It uses the same canonical semantic envelope as live Agent and Network events. Its `sequence` is the high-watermark represented by the snapshot.

### Incremental events

After `run.state`, only events newer than the captured high-watermark are sent. Public output deltas use the existing token semantics. Internal/debug/private events are sanitized or suppressed from the public projection.

### Heartbeat

Heartbeat keeps long-lived connections active and is a transport frame, not part of the semantic event history and not part of semantic sequence ordering.

### Terminal state

A public terminal event/state is emitted only after durable Finalization has succeeded. Woobe must not advertise `completed` in Redis and then discover that the PostgreSQL finalization failed.

Terminal statuses include:

- `completed`;
- `failed`;
- `cancelled`;
- `timed_out`;
- `uncertain` when the runtime cannot safely assert the external outcome.

If Redis data has expired for a terminal Run, the reattach endpoint synthesizes canonical `run.state` from the durable PostgreSQL result and closes the stream.

## Cancellation

Transport disconnect is not cancellation.

```text
close browser / F5 / network loss / SSE abort
→ unsubscribe observer
→ Run continues
```

Cancellation requires an explicit Run operation or a runtime policy. Agent cancellation is represented by the hot cancellation flag and is finalized durably by the execution owner. The Playground Stop action calls the explicit Agent Run cancellation endpoint. Network Stop continues to call the explicit Network execution cancellation path.

## Failure and degradation

Realtime infrastructure must not become business truth.

For standalone Agent execution, hot-state writes are best-effort: a Redis publication failure may degrade realtime observation, but it does not rewrite a successful model execution as failed. Durable finalization still owns the Run outcome.

For Network execution, Redis remains part of the active orchestration store. After PostgreSQL finalization has succeeded, failure to publish the final Redis event is treated as realtime degradation rather than a failed Network Run.

Clients can receive `run.realtime_unavailable` or a `run.state` with `realtime_available: false` when only durable state is available. These are transport/degradation signals and do not create a second business outcome for the Run.

## Worker recovery boundary

Reattach is not equivalent to replaying arbitrary external side effects.

The existing Network lease recovery worker remains intentionally conservative:

- `terminal_pending_persist` can be finalized because execution already reached a terminal runtime boundary;
- a queued durable execution without hot state may still be waiting for worker admission and is not replayed speculatively;
- loss of hot state after external execution started is finalized as `uncertain` when safe continuation cannot be proven;
- expired leases with materialized invocations are not replayed blindly.

This is the correct MVP boundary. Arbitrary checkpoint/resume of model calls, Tools, HTTP side effects or delegated Agents would require resumability/idempotency contracts at every external boundary. Reattach solves observer continuity without creating duplicate side effects.

## Reattach observability

No new metrics backend is required for the MVP. The runtime emits structured operational logs and maintains the hot reconnect counter.

State-resolution telemetry includes:

- `run_id` and Run kind;
- realtime availability;
- high-watermark;
- saved projection sequence;
- projection lag;
- catch-up event count;
- reattach count;
- attach latency in milliseconds.

Stream-close telemetry includes:

- terminal/close reason;
- frame count;
- live event count;
- approximate SSE bytes;
- stream duration.

Projection gaps and realtime-tail degradation are warning events. These fields are sufficient to feed the existing logging/observability pipeline without introducing Prometheus/Kafka/Event Sourcing solely for this feature.

## Security and visibility

Public runtime streams do not expose Redis keys, infrastructure cursors, credentials, authorization headers, provider secrets, hidden reasoning, or unrestricted Tool payloads.

Runtime events are projected through a public visibility/redaction layer. Tool inputs/outputs and internal Agent activity require explicit safe representations before they can appear in a public projection. Administrative Debug/Trace views may use richer authorized data, but they are not the public chat contract.

ChatSurface reattach remains bound to the existing Session token, target release, Surface, Project, Session and host origin. Runtime API reattach remains bound to the Runtime Key target/environment.

## Client rules

Consumers should:

1. treat `run.state` as replacement/current-state reconciliation;
2. ignore events at or below the local logical sequence;
3. apply contiguous newer events incrementally;
4. reattach instead of guessing when a sequence gap is detected;
5. distinguish transport failure from Run failure;
6. retain canonical `run_id` and `session_id` as soon as a semantic event is observed;
7. consume domain-specific data from the canonical `payload` rather than reconstructing identity from aliases;
8. use explicit cancel when the user requests Stop;
9. use durable Session/message history for terminal Runs after hot retention expires;
10. never recover transport by submitting another logical execution once Run identity is known.

The Standalone Playground remembers terminal Run identities for the mounted page.
Rediscovering one of those Runs through a lagging read model must not start another
observer. Transport retries remain bounded by the shared runtime client; React
effects must not restart that retry budget after observer exhaustion. A new Session
visit or page reload can recover an interrupted observer without creating a Run.

Active Agent Run discovery is wired to the durable journal, so a terminal fact in
its contiguous durable prefix excludes a stale PostgreSQL `running` row. A pending
terminal event outside that prefix does not establish completion. The persistence
worker projects every journal page through the durable watermark before acknowledging
buffered events; a failed or missing page remains retryable.

Terminal failure snapshots carry public diagnostics under `error`, including
`failure_code` and `trace_id`. Clients use those fields for actionable error messages;
raw internal/provider exception text remains excluded from public journal replay.

The central rule is: **the Run belongs to the runtime; the connection belongs to the observer.**
