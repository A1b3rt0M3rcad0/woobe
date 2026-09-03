# Unified Runtime Observer

This document records the runtime observation boundary used by Agent Runs, Network Runs and ChatSurface consumers.

## Invariant

A Run belongs to the runtime. A connection belongs to an observer.

Closing an SSE connection, refreshing a browser, navigating away or losing connectivity must never cancel, restart or duplicate the underlying Run. Cancellation is an explicit Run operation.

## Canonical vocabulary

`shared.runtime` defines the transport-neutral runtime observation language:

- `RunKind`: `agent` or `network`;
- `RunReference`: stable Run identity plus kind;
- `RunStatus`: canonical lifecycle status vocabulary;
- `RuntimeFrame`: event type, public data and optional logical sequence;
- `RuntimeObserver`: the only boundary used by runtime consumers to observe current state and live progress.

Agent and Network keep different executors. The unification is limited to observation and Run lifecycle vocabulary; it does not create a generic Agent/Network executor.

## Observation sources

The observer supports two sources without changing the public frame language.

### Initial Agent fast path

The initial Agent POST subscribes to the local `RuntimeStreamChannel` before execution starts. This preserves TTFT and does not require a Redis round trip before already-produced model tokens can reach the client.

The local subscription owns only its observer queue. Disconnecting it does not own or cancel execution. A separate persistence pump continues projecting the same runtime events into hot state for later reattach.

### Canonical reattach

Agent, Network and ChatSurface reattach use the shared hot-state reader behind `RuntimeObserver`:

```text
saved projection
      +
events through captured high-watermark
      ↓
run.state @ H
      ↓
live events > H
```

If retained events cannot bridge the saved projection, observation degrades explicitly instead of inventing continuity. PostgreSQL remains authoritative for durable terminal state.

## Consumer boundaries

The following consumers use the same observer semantics:

- standalone Agent initial stream;
- standalone Agent reattach;
- Network reattach;
- Network compatibility stream used by existing surfaces;
- ChatSurface active-Run reattach;
- Public Runtime API reattach through the Agent/Network public boundaries.

The Public Runtime API dispatches target-specific execution through the `woobe-api` composition root. Target dispatch is not part of the shared runtime domain.

## Compatibility

Existing HTTP endpoints and SSE envelopes remain stable. Network frames are still adapted into the current Network event envelope. `run.state` keeps replacement semantics, logical sequence remains independent from Redis cursor identity, and transport disconnect remains observer-only.

## Failure model

Realtime infrastructure is not business truth. Redis/event delivery failure can degrade live observation but must not turn a successfully finalized Run into a failed Run. Terminal public state is derived from durable finalization when hot state is absent or expired.
