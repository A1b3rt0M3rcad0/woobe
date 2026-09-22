# Standard and Adaptive

Woobe ships two built-in Context Manager algorithms with deliberately different behavior.

## Comparison

| Capability | Standard | Adaptive |
| --- | --- | --- |
| Async contract | yes | yes |
| Extra model calls for context | never | only when Summary Policy triggers |
| Typed Manager State | empty base state | `AdaptiveContextState` |
| Capacity-aware algorithm decisions | Runtime enforcement only | yes |
| Candidate inventory-aware decisions | not required | yes |
| Semantic summary | no | pressure-triggered or rolling |
| Incremental summary refresh | no | yes |
| Context checkpoint | normally no | after new/refreshed summary |
| Summary failure fallback | n/a | configurable |
| Skills | materializes active Skills | capacity-aware active-Skills decision |
| Deterministic caps/dedup/order | yes | yes |
| Context Snapshot evidence | yes | yes |

## Standard

Standard is the baseline deterministic algorithm.

~~~text
configured Context Policy
        ↓
allowed sources
Session window
per-source caps
priorities
deduplication/order
budget enforcement
Skills materialization
        ↓
ContextSnapshot
~~~

It does not call `ctx.summary`, does not need durable Manager state and does not introduce extra provider calls.

Use Standard when predictability/minimum cost is more important than preserving very long historical context.

## Adaptive

Adaptive starts from the same policy/invariants and adds algorithmic adaptation.

It inspects:

~~~text
ctx.capacity
ctx.inventory
ctx.invocation
~~~

It scales source caps relative to usable invocation budget, including smaller fallback model windows.

When `summary.strategy` is enabled, Adaptive may:

~~~text
inspect eligible historical source
        ↓
reuse checkpointed summary when valid
        ↓
create or incrementally refresh summary when trigger is met
        ↓
store ContextSummaryResult in AdaptiveContextState
        ↓
await context summary checkpoint
        ↓
materialize summary + preserved recent tail
~~~

## Pressure-triggered example

If usable input is 16k units and the candidate inventory reaches the configured pressure trigger, Adaptive can compress old Session history to a 2k summary while preserving the newest eight Session messages verbatim.

## Rolling example

On the first threshold, raw old history becomes summary S1. After enough new historical messages accumulate, refresh sends S1 plus only the new eligible history and produces S2. S2 lineage covers the entire represented source set.

## What Adaptive does not mean

Adaptive is not a general autonomous Agent. It does not choose Tools, query arbitrary providers or write databases. It is still a Context algorithm constrained to the Context Manager SDK.

## Selection guidance

`standard` is the safe default and historical fallback.

`adaptive` is intended for context-heavy or long-running Run execution where preserving semantic history can justify extra summary model calls.

Cross-Run Session-long rolling summary is not yet automatic; current Adaptive state is Run-local.
