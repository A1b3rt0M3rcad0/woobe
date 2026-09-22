# Summary and compaction

Semantic summary is a real missing capability in the current Context Manager Runtime. It must not be confused with the existing `compaction_*` metrics.

## What compaction means today

Woobe currently reduces materialized context through:

1. candidate exclusion;
2. recent Session selection;
3. content-hash deduplication;
4. per-source caps;
5. text truncation;
6. structured External Context compaction;
7. upstream Tool-output compaction whose transformation metadata is preserved.

`compaction_saving_units` measures raw-versus-materialized savings for selected contributions. It does **not** mean that an LLM summary was generated.

## What semantic summary would add

A summary capability would need to support at least:

~~~text
semantic compression of old Session turns
rolling or pressure-triggered summaries
source lineage
summary refresh/staleness rules
summary model selection
cost and usage accounting
failure/fallback behavior
durability and recovery semantics
summary-specific transformation evidence
~~~

None of those mechanics exist in the current Runtime.

## Why there is no `ctx.summary()` primitive yet

The outer `ContextAssembler.assemble()` boundary is synchronous. Semantic summary normally requires asynchronous model I/O.

Hiding a provider call inside a synchronous Manager primitive would introduce:

- blocking I/O inside the execution loop;
- uninstrumented model calls;
- missing cost/usage accounting;
- unclear retry/fallback semantics;
- recursive context-assembly risk;
- no durable boundary around summary generation;
- ambiguous recovery behavior.

That would violate the same runtime/algorithm separation already enforced for Execution Strategies.

## Correct future architecture

The preferred extension is a deterministic planning step followed by an async runtime transformation step:

~~~text
Manager algorithm
      │
      │ returns ContextPlan / transformation intents
      ▼
Context Manager Runtime
      │
      ├── executes reusable async transformations
      │     └── semantic summary capability
      │
      ├── records usage/cost/provenance
      └── materializes final context
~~~

The Manager itself can remain deterministic while Runtime owns asynchronous execution mechanics.

## Proposed Summary Policy

When the runtime capability exists, Summary Policy should answer deterministic questions such as:

~~~text
strategy
eligible source types
trigger condition
target summary units
recent tail preserved verbatim
refresh threshold
failure mode
summary model selection policy
retention/persistence policy
~~~

A plausible future shape is:

~~~python
class ContextSummaryPolicy(BaseModel):
    strategy: Literal["disabled", "pressure_triggered", "rolling"] = "disabled"
    sources: list[ContextSourceType] = [ContextSourceType.SESSION]
    trigger_at: float = 0.75
    target_units: int = 2_000
    preserve_recent_messages: int = 8
    refresh_after_messages: int = 12
    failure_mode: Literal["fallback_to_selection", "fail"] = "fallback_to_selection"
~~~

This is a design target, not an implemented schema/runtime contract in the current branch.

## Provenance requirements

A future semantic summary contribution should preserve:

~~~text
source refs of summarized contributions
raw source units
summary units
summary model/provider identity
summary model call id
transformation = semantic_summary
summary policy hash
generation timestamp
integrity hash
~~~

A summary must appear as an explicit transformation in Context evidence, never as unexplained replacement text.

## Summary versus Memory

Summary and Memory are distinct:

- Summary compresses selected context for an invocation or conversation window.
- Memory is a reusable persisted knowledge source that may outlive that window.

A rolling Session summary may later be persisted through a checkpoint or memory subsystem, but that persistence decision should be explicit.
