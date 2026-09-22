# Context evidence and observability

Programmability must not make context behavior opaque. Runtime records materialization evidence for every instrumented Model Invocation and records semantic-summary model calls separately.

## ContextSnapshot

A `ContextSnapshot` captures the effective materialization decision:

~~~text
project/Run/Model Invocation identity
policy schema/hash
model capacity and reserves
usable input budget
estimated/reported input units
utilization and pressure status
measurement status
materialized hash
retention/reproduction metadata
ContextContribution list
manifest
~~~

Concrete Managers never construct Snapshots directly.

## ContextContribution

Each contribution records source, refs, modality, priority, units, selection method, transformations, integrity and metadata.

## Semantic-summary contribution

A semantic summary retains its original source type and includes transformation provenance:

~~~text
source_type = SESSION | CHECKPOINT | MEMORY | KNOWLEDGE | ARTIFACT
selection_method = semantic_summary
transformations = [semantic_summary]
raw_units = units of represented raw sources
materialized_units = summary units
summary_source_refs
summary_source_hash
summary_model_invocation_id
summary_provider
summary_model
~~~

This means source-share and compaction metrics can continue to attribute the summary to the source knowledge it represents.

## Summary model call

The provider call that creates or refreshes a summary appears in execution `llm_calls`/timeline with:

~~~text
purpose = context_summary
phase = context_summary
parent_call_index
parent_model_invocation_id
provider/model
latency
input/output/total tokens
cost
status
~~~

It is an internal model call and is not streamed as assistant output.

## Context checkpoints

`await ctx.checkpoint(...)` emits durable `context.checkpoint` evidence. The payload contains Manager identity, boundary and serialized typed state.

Normal `execution.checkpoint` state also embeds the current Context Manager state so recovery continuations preserve algorithm state.

## Selection/exclusion metrics

Shared deterministic assembly still records candidate counts/units, selected counts/units, selection ratio, compaction savings, truncation, configured/effective budget, budget clamp, headroom and fit status.

Exclusion reasons remain explicit, including source-not-allowed, Session window, deduplication, source cap and global budget.

## Estimated versus reported measurement

Woobe estimates input units before provider execution. Provider-reported input usage may later enrich the Snapshot. Opaque/multimodal context remains `PARTIAL` instead of pretending all modalities are exactly token-comparable.

## Invariant

> Different Context Manager algorithms may select and transform different material, but they must preserve a shared evidence contract.
