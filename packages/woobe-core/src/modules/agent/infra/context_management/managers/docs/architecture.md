# Architecture and mental model

A Context Manager is Woobe's programmable algorithm for managing Model Invocation context. The contract is asynchronous because a Manager may request runtime-owned asynchronous capabilities such as semantic summary and durable checkpointing.

The concrete Manager decides **what should happen**. Context Manager Runtime owns **how side effects and materialization happen**.

## Dependency direction

~~~text
Concrete Context Manager
        │
        ▼
async assemble(ctx)
        │
        ├── ctx.policy       configured policy input
        ├── ctx.state        typed algorithm state
        ├── ctx.capacity     invocation/model budget facts
        ├── ctx.inventory    aggregate candidate facts
        ├── ctx.invocation   phase/provider/model/delegation/tool facts
        ├── ctx.candidates   eligibility/window/caps/dedup/order
        ├── ctx.priorities   source priority decisions
        ├── ctx.budget       input budget/runtime reserve
        ├── ctx.pressure     evidence thresholds
        ├── ctx.sources      optional runtime-owned materializers
        ├── ctx.summary      semantic-summary capability
        ├── await ctx.checkpoint(...)
        └── ctx.complete()
                 │
                 ▼
Context Manager Runtime
        ├── effective-policy isolation and validation
        ├── Manager State serialization/restoration
        ├── semantic-summary model execution
        ├── durable Context checkpoints
        ├── optional source materialization
        ├── External Context projection
        ├── model-capacity/output-reserve clamp
        ├── mandatory-source enforcement
        ├── deterministic trimming/exclusion
        ├── provider-safe message assembly
        ├── Context Snapshot/Contribution evidence
        └── provenance/integrity accounting
                 │
                 ▼
async ContextAssembler boundary
                 │
                 ▼
Model Invocation
~~~

That is deliberately parallel to Execution:

~~~text
Execution Strategy -> StrategyContext        -> Strategy Runtime
Context Manager    -> ContextManagerContext -> Context Manager Runtime
~~~

## Algorithm versus mechanics

A Manager may decide that a Session should be summarized, but it must not call a provider directly:

~~~python
summary = await ctx.summary.create(
    ContextSourceType.SESSION,
    target_units=2_000,
    preserve_recent_messages=8,
)
await ctx.checkpoint(ContextCheckpointBoundary.SUMMARY)
~~~

`ctx.summary` executes through Runtime. Runtime owns the provider call, usage/cost accounting, trace evidence, source lineage and the actual transformation.

A Manager must never import provider clients, LangChain message classes, database repositories or journal implementations.

## Why the Manager itself is async

The async boundary lets algorithms compose reusable runtime capabilities without blocking or inventing a second execution system. Standard is still cheap: it is `async` but performs no additional model I/O and normally never checkpoints.

Adaptive uses the same contract and may await summary/checkpoint primitives when policy and context conditions require them.

Do not maintain separate SyncContextManager and AsyncContextManager contracts.

## Configured policy versus effective policy

`ctx.policy` is an isolated configured snapshot. SDK mutation primitives operate on a separate effective copy.

~~~text
configured ContextPolicyV1
          │ read
          ▼
Manager algorithm
          │ SDK decisions
          ▼
effective ContextPolicyV1
          │
          ▼
Runtime materialization
~~~

Directly mutating `ctx.policy` does not program runtime behavior.

## State model

Every Manager declares `state_type`.

Standard uses the empty base `ContextManagerState`. Adaptive uses `AdaptiveContextState`, which currently persists summary metadata/content and `summary_generation`.

State is run-local hot state and can be durably checkpointed. It is not stored on the Manager instance, because built-in Manager instances may be reused across concurrent Runs.

## Context checkpoint versus Context Snapshot

These are different artifacts:

~~~text
ContextSnapshot
= evidence of the exact context materialized for one Model Invocation

context.checkpoint
= durable serialized Context Manager algorithm state used by later invocations/recovery
~~~

A Context checkpoint does not by itself become a causal execution continuation checkpoint. During recovery, Woobe overlays the newest durable Context Manager state onto the latest safe `execution.checkpoint`; if no execution checkpoint exists and the durable prefix has no unsafe Tool side effect, execution may restart from the beginning while reusing Context Manager state.

## Summary transformation model

Semantic summary preserves the original source type. Summary is a transformation, not a new source ontology.

~~~text
SESSION messages
      │ semantic_summary
      ▼
SESSION contribution
  transformations = [semantic_summary]
~~~

The contribution carries source refs/hash, raw/materialized units and summary model provenance.

## Adding a new primitive

Add a primitive only when several algorithms need an operation and Runtime can give it precise, observable semantics. Side effects, I/O, durability and provider behavior belong behind Runtime primitives.

Adding a normal Manager must not require a private Manager-specific runtime package.
