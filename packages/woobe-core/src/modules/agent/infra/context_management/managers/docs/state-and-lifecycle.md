# State and lifecycle

A Context Manager is currently a **per-Model-Invocation deterministic algorithm**. It does not own durable Manager State analogous to `ExecutionState`.

## Invocation lifecycle

~~~text
Run preparation
    ↓
available context sources + ContextPolicyV1
    ↓
one Model Invocation begins
    ↓
ContextManagerContext is created
    ↓
Manager programs effective policy
    ↓
Context Manager Runtime materializes context
    ↓
ContextSnapshot is recorded
    ↓
Model is invoked
~~~

A new `ContextManagerContext` is created for every Model Invocation, including Tool follow-ups, final-response generation and repair invocations.

## What may vary per invocation

The same Agent Run can invoke different models or phases with different effective capacities.

Runtime therefore recomputes:

~~~text
model context capacity
effective output reserve
usable input budget
selected/materialized context
ContextSnapshot
pressure classification
~~~

A fallback model with a smaller context window can receive a smaller re-materialized context without changing the Agent's configured Context Policy.

## What does not belong on the Manager instance

Do not store per-Run or per-invocation mutable values such as:

~~~text
previous messages
selected contribution ids
summary text
current pressure
current budget
Skill activation state
Model invocation ids
ContextSnapshot ids
~~~

Built-in Manager instances may be shared across concurrent Runs.

## Where persistent context state belongs

Long-lived information should live in the subsystem that owns its semantics:

- Session history belongs to Session/message persistence.
- Execution checkpoint state belongs to execution/recovery.
- Memory belongs to a memory capability/store.
- Skill activation state belongs to the Run-local Skills runtime.
- Knowledge versions and vector snapshots belong to Knowledge/RAG.
- Future rolling summaries need an explicit persistence contract if they survive one invocation.

## Why there is no ContextManagerState today

The current Standard algorithm does not need algorithm-local durable state. Every decision can be derived from configured policy, available sources and invocation capacity.

Do not introduce a generic Manager State abstraction preemptively.

If a future algorithm genuinely needs durable decision state across invocations, the design should answer:

~~~text
what changes future Manager decisions?
when is it checkpointed?
who serializes it?
how is it restored?
how does it interact with Release immutability?
how does replay avoid duplicated side effects?
~~~

Only then should a shared Context Manager State contract be introduced.

## Summary is not Manager State by default

A semantic summary is context data/transformation output, not automatically Manager algorithm state.

If persisted, it should carry source lineage and live in an explicit Session/checkpoint/memory persistence model rather than as an opaque field on the Manager object.
