# Architecture and mental model

A Context Manager is the algorithm that decides **which context is eligible, how it is prioritized, how much may be materialized, and which runtime-owned optional sources participate before one Model Invocation**.

The Manager should read like context-selection algorithm code, not provider, persistence or message-construction code.

## Dependency direction

~~~text
Concrete Context Manager
        │
        ▼
ContextManagerContext
├── policy          configured input, isolated from effective behavior
├── candidates      eligibility, Session window, caps, dedup, ordering
├── capacity        invocation/model budget facts
├── inventory       aggregate candidates by source
├── invocation      phase/provider/model/delegation/tool facts
├── priorities      source priority decisions
├── budget          configured input budget and runtime reserve
├── pressure        evidence/classification thresholds
├── sources         optional runtime-owned materializers
└── complete()
        │
        ▼
Context Manager Runtime
├── effective-policy isolation
├── optional source materialization
├── External Context projection
├── model-capacity clamping
├── mandatory-source enforcement
├── deterministic trimming/exclusion
├── provider-safe message assembly
├── Context Snapshot generation
├── contribution provenance
└── integrity/hash accounting
        │
        ▼
ContextAssembler boundary
        │
        ▼
Model Invocation
~~~

This mirrors Execution Strategy:

~~~text
Execution Strategy -> StrategyContext       -> Strategy Runtime
Context Manager    -> ContextManagerContext -> Context Manager Runtime
~~~

## What a Manager owns

A Manager can inspect invocation capacity through `ctx.capacity`, aggregate source availability through `ctx.inventory`, and algorithm-relevant invocation metadata through `ctx.invocation`, without receiving the outer request or provider message objects.

Typical Manager decisions include:

~~~text
allowed source set
Session history window
per-source caps
source priorities
deduplication
ordering
configured input budget
runtime reserve
pressure evidence thresholds
optional runtime-owned source participation
~~~

## What the Runtime owns

A concrete Manager must assume these concerns are already handled:

~~~text
provider/LangChain message classes
External Context contract projection
model capacity and output reserve
mandatory SYSTEM/current-input invariants
safe text and structured-data trimming
global overflow handling
Skills materialization mechanics
Context Snapshot construction
ContextContribution construction
selection/exclusion metrics
transformation provenance
integrity hashes
measurement status
pressure status
~~~

Normal Manager code therefore looks like:

~~~python
policy = ctx.policy
ctx.candidates.allow(policy.allowed_sources)
ctx.priorities.configure(policy.source_priorities)
ctx.candidates.recent_session(
    max_messages=policy.session.max_messages,
    max_units=policy.session.max_units,
)
ctx.budget.configure(
    max_input_units=policy.budget.max_input_units,
    runtime_reserve_units=policy.budget.runtime_reserve_units,
)
return ctx.complete()
~~~

## Configured policy versus effective policy

`ctx.policy` is the configured policy snapshot supplied to this invocation. It is algorithm input.

The Runtime creates a separate effective policy. SDK primitives mutate only the effective copy, and `ctx.complete()` returns that result. Direct mutation of `ctx.policy` does not program runtime behavior.

~~~text
configured policy
      │ read
      ▼
Manager algorithm
      │ SDK decisions
      ▼
effective policy
      │
      ▼
runtime materialization
~~~

This prevents concrete Managers from bypassing the supported primitive surface.

## Concurrency

A runtime host may reuse the same Manager instance across concurrent Runs. Per-invocation mutable state belongs in `ContextManagerContext`, never on the Manager instance.

Managers should be stateless unless they hold immutable algorithm configuration.

## When Runtime should change

Adding a normal Manager should not require changes under `infra/context_management/manager_runtime/`.

If a requirement is specific to one algorithm, keep it in that Manager. If several Managers need the same operation and Runtime can give it precise reusable semantics, add a small SDK + Runtime primitive.

If a capability requires asynchronous I/O, durability, instrumentation or provider behavior, it needs an explicit runtime execution boundary. Model-based summary is the clearest current example.

> Do not add a primitive unless Runtime can give it precise, observable semantics.
