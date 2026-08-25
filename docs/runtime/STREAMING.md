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

## Redis responsibilities

Redis is hot operational state, not the durable source of truth. It stores:

- in-flight execution state;
- ordered runtime events;
- runtime projection checkpoints;
- cancellation flags and execution coordination where applicable;
- short-lived data required for reattach.

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

Explicit cancellation is independent from stream disconnect:

```text
POST /runtime/runs/{run_id}/cancel
```

The Agent client never automatically submits a second POST after a Run ID is known. A transport interruption becomes a reattach operation.

## Network endpoints

The existing Network streaming POST remains a convenience create-and-observe entrypoint. The canonical Network Run can be observed independently through:

```text
GET /network/executions/{execution_id}/stream
```

Once the Network execution ID is known, the web client switches transport retries to this GET endpoint. Before the ID is available, the existing Network idempotency key is reused so retries resolve to the same logical Network Run.

Network execution is already worker-owned; observer disconnects do not own worker cancellation.

## SSE frames

### `run.state`

`run.state` is the initial replacement frame for an attach/reattach operation. It contains the effective current public projection, including the current output and status. For Network consumers it is wrapped in the existing `NetworkRuntimeEvent` envelope so the public protocol remains compatible.

### Incremental events

After `run.state`, only events newer than the captured high-watermark are sent. Public output deltas use the existing token semantics. Internal/debug/private events are sanitized or suppressed from the public projection.

### Heartbeat

Heartbeat keeps long-lived connections active and is not part of the semantic event history.

### Terminal state

A public terminal event/state is emitted only after durable Finalization has succeeded. Woobe must not advertise `completed` in Redis and then discover that the PostgreSQL finalization failed.

Terminal statuses include:

- `completed`;
- `failed`;
- `cancelled`;
- `timed_out`;
- `uncertain` when the runtime cannot safely assert the external outcome.

If Redis data has expired for a terminal Run, the reattach endpoint synthesizes `run.state` from the durable PostgreSQL result and closes the stream.

## Cancellation

Transport disconnect is not cancellation.

```text
close browser / F5 / network loss / SSE abort
→ unsubscribe observer
→ Run continues
```

Cancellation requires an explicit Run operation or a runtime policy. Agent cancellation is represented by the hot cancellation flag and is finalized durably by the execution owner. Network cancellation continues to use its explicit execution control path.

## Failure and degradation

Realtime infrastructure must not become business truth.

For standalone Agent execution, hot-state writes are best-effort: a Redis publication failure may degrade realtime observation, but it does not rewrite a successful model execution as failed. Durable finalization still owns the Run outcome.

For Network execution, Redis remains part of the active orchestration store. After PostgreSQL finalization has succeeded, failure to publish the final Redis event is treated as realtime degradation rather than a failed Network Run.

Clients can receive `run.realtime_unavailable` or a `run.state` with `realtime_available: false` when only durable state is available.

## Security and visibility

Public runtime streams do not expose Redis keys, infrastructure cursors, credentials, authorization headers, provider secrets, hidden reasoning, or unrestricted Tool payloads.

Runtime events are projected through a public visibility/redaction layer. Tool inputs/outputs and internal Agent activity require explicit safe representations before they can appear in a public projection. Administrative Debug/Trace views may use richer authorized data, but they are not the public chat contract.

## Client rules

Consumers should:

1. treat `run.state` as replacement/current-state reconciliation;
2. ignore events at or below the local logical sequence;
3. apply contiguous newer events incrementally;
4. reattach instead of guessing when a sequence gap is detected;
5. distinguish transport failure from Run failure;
6. retain the canonical `run_id`/`execution_id` as soon as it is observed;
7. use explicit cancel when the user requests Stop;
8. use durable Session/message history for terminal Runs after hot retention expires.

The central rule is: **the Run belongs to the runtime; the connection belongs to the observer.**
