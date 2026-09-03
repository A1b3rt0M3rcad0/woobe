# Unified Runtime and Observer Boundaries

This document records the runtime execution and observation boundaries used by Agent Runs, Network Runs, the Public Runtime API, ChatSurface and browser/embed consumers.

## Core invariants

A Run belongs to the runtime. A connection belongs to an observer.

Closing an SSE connection, refreshing a browser, navigating away or losing connectivity must never cancel, restart or duplicate the underlying Run. Cancellation is an explicit Run operation.

The runtime has one canonical execution per accepted Run. ChatSurface, Playground, Network UI, Embed and Public Runtime API are consumers of that execution; they are not independent runtimes.

Agent and Network remain different bounded contexts with different executors. The unification deliberately stops at Run identity, observation, lifecycle semantics and external consumption. It does not create a generic Agent/Network executor.

## Canonical vocabulary

`shared.runtime` defines the transport-neutral observation language:

- `RunKind`: `agent` or `network`;
- `RunReference`: stable Run identity plus kind;
- `RunStatus`: canonical lifecycle status vocabulary;
- `RuntimeFrame`: event type, public data and optional logical sequence;
- `RuntimeObserver`: the canonical boundary for current state and live progress.

Logical event sequence is part of the runtime protocol. Redis stream cursor identity is an implementation detail and must not leak into the public contract.

## Execution ownership

Execution remains target-specific:

```text
consumer
   │
   ▼
composition boundary
   ├── Agent runtime executor
   └── Network runtime executor
```

The process composition roots own cross-context wiring:

- `woobe-api` owns Public Runtime API dispatch and `ApiChatRuntimeGateway`;
- `woobe-workers` owns the Network -> Agent runtime adapter required by Network execution;
- `shared.runtime` contains no Agent/Network dispatch logic.

This prevents a shared runtime abstraction from becoming a second application layer or a hidden generic executor.

## Observation sources

The observer supports different physical sources without changing the public frame language.

### Initial Agent fast path

The initial Agent POST subscribes to the local `RuntimeStreamChannel` before execution starts. This preserves TTFT and does not require a Redis round trip before already-produced model tokens can reach the client.

The local subscription owns only its observer queue. Disconnecting it does not own or cancel execution. A separate persistence pump continues projecting the same runtime events into hot state for later reattach.

### Acceptance to hot-state window

Durable Acceptance and runtime hot-state materialization are separate boundaries. An observer must not conclude that a Run disappeared merely because the durable Run exists before its Redis projection is available.

During this window the observer remains attached until one of the following becomes true:

- hot runtime state materializes and observation continues normally;
- durable state becomes terminal;
- the consumer disconnects, which closes only that observer.

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

The replacement `run.state` is authoritative for current reconstructed output. Consumers do not replay every event already represented by that snapshot.

Example:

```text
client last observed 125
runtime advanced through 126..131
reconnect
   ↓
run.state @131
   ↓
132
133
...
```

If retained events cannot bridge the saved projection, observation degrades explicitly instead of inventing continuity. PostgreSQL remains authoritative for durable terminal state.

## ChatSurface boundary

ChatSurface owns:

- public/session authentication;
- origin and scope enforcement;
- Session binding to immutable Agent/Network release;
- message admission and idempotency bookkeeping;
- Surface-wide concurrency policy;
- presentation-specific response headers and API shape.

ChatSurface does **not** own Agent or Network execution.

`ChatRuntimeGateway` is the neutral application contract used by ChatSurface for:

- preparing a new canonical execution;
- resolving the canonical Run for a Session/message request;
- observing an existing Run;
- requesting Run cancellation.

`ApiChatRuntimeGateway`, composed by `woobe-api`, owns the target-specific Agent/Network implementation. ChatSurface presentation and lifecycle code must not query `AgentRunModel` or `NetworkExecutionModel` directly.

Target-aware Session/Release validation remains inside ChatSurface because it validates the Surface binding itself, not runtime execution ownership.

## MessageRequest lifecycle

`ChatSurfaceMessageRequest` is admission and correlation bookkeeping. It is not the source of truth for execution state.

The canonical Run owns lifecycle truth.

Consequences:

- transport EOF does not complete a message;
- browser disconnect does not fail a message;
- an observer exception does not automatically fail a message;
- `completed`, `cancelled` or `failed` is applied only after a canonical terminal Run fact is observed or resolved;
- an accepted request that never acquires a canonical Run is released after the bounded acceptance grace period with `run_acceptance_missing`;
- stale admission leases are reconciled against canonical Run state before new Surface capacity is rejected.

This prevents a dead SSE connection from poisoning Session concurrency or causing duplicate logical execution.

## Public Runtime API

The Public Runtime API is another surface over the same canonical runtime.

The API composition root selects Agent or Network from Runtime Key binding. Shared runtime code remains unaware of target-specific controllers/services.

Supported observation/control operations use the same Run identity semantics:

- start Run;
- start streaming Run;
- reattach Run;
- resolve active Session Run;
- cancel Run.

A reattach or cancel operation never creates another Run.

## Browser and Embed runtime protocol

Browser consumers share the same runtime protocol policy:

- protocol version validation;
- `run.state` replacement semantics;
- logical sequence acceptance;
- duplicate/stale event rejection;
- gap detection;
- durable snapshot handling when realtime state is unavailable;
- terminal status classification;
- snapshot output append/replacement calculation;
- bounded observer retry/backoff.

`packages/woobe-frontend/src/lib/runtime-stream.ts` is the canonical protocol module for the Woobe web application. Both Agent Playground and Network streaming consume it.

`packages/woobe-embed/src/runtime-stream.ts` is the equivalent bundled protocol module for the independent Embed artifact. The two packages intentionally remain separately buildable, while architecture gates require the same protocol primitives and policy constants so their semantics cannot silently diverge.

UI-specific rendering remains outside the protocol module. Network invocation/delegation hydration, Agent activity rendering and Embed DOM updates are presentation concerns.

## Sequence semantics

For incremental frames:

- sequence lower than or equal to the last accepted sequence is stale/duplicate and is ignored;
- sequence greater than `last + 1` is a gap and forces reconciliation/reattach;
- accepted sequence advances only after a contiguous frame.

For `run.state`:

- a newer snapshot can jump the consumer directly to its high watermark;
- an older hot snapshot is ignored rather than rewinding the client;
- a durable-only snapshot with `realtime_available=false` is accepted as authoritative business state but does not rewind the last known hot sequence.

## Cancellation

Cancellation is an explicit control operation on a Run.

Agent cancellation is recorded against active runtime control state and later persisted as canonical Run terminal state. Network cancellation delegates to the Network application service. ChatSurface only authorizes the request and routes it through `ChatRuntimeGateway`.

A missing/unavailable active control state fails closed: the system must not report cancellation as requested when it cannot durably or safely establish that fact.

## Failure model

Realtime infrastructure is not business truth.

Redis/event delivery failure can degrade live observation but must not turn a successfully finalized Run into a failed Run. Terminal public state is derived from durable finalization when hot state is absent or expired.

The system distinguishes:

- execution failure: canonical Run failed;
- cancellation: canonical Run was cancelled;
- timeout/uncertain terminal state: canonical terminal outcome with explicit semantics;
- observation failure: one consumer lost realtime continuity;
- hot-state unavailability: realtime projection unavailable while durable Run state remains authoritative.

Only the first four canonical Run terminal statuses terminate business execution. Observation failure only terminates that observer.

## Quality gates

Architecture tests protect the boundary against regression:

- ChatSurface runtime presentation cannot import Agent/Network runtime implementation;
- ChatSurface Control Plane lifecycle cannot resolve Agent/Network Runs directly through target ORM models;
- API/worker composition modules own cross-context runtime adapters;
- Runtime Observer contracts stay in `shared.runtime`;
- frontend Agent and Network consumers must use the canonical frontend runtime protocol module;
- frontend and Embed protocol modules must expose the same protocol primitives and policy constants;
- app-specific clients cannot reimplement the logical sequence gap algorithm.

## Resulting architecture

```text
                         ┌────────────────────┐
                         │ canonical Run truth │
                         │ durable + hot state │
                         └─────────┬──────────┘
                                   │
                         ┌─────────▼──────────┐
                         │  RuntimeObserver   │
                         │ state + live tail  │
                         └─────────┬──────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
         Agent surfaces       Network surfaces      ChatSurface
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   │
                       frontend/embed protocol
                                   │
                                users
```

Execution remains Agent- or Network-specific below the composition boundary. Consumption and observation use one Run model and one set of runtime semantics above it.
