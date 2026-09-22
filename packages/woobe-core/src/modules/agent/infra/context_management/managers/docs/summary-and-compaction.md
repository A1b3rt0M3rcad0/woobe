# Summary and compaction

Woobe now supports semantic summary as a first-class asynchronous Context Runtime capability. It is distinct from deterministic context reduction.

## Deterministic compaction

Existing context reduction still includes:

1. source exclusion;
2. recent Session selection;
3. content-hash deduplication;
4. per-source caps;
5. text truncation;
6. structured External Context compaction;
7. upstream Tool-output compaction.

`compaction_saving_units` can reflect these deterministic transformations. It must not be interpreted as proof of an LLM-generated summary.

## Semantic summary

A Manager may now call:

~~~python
summary = await ctx.summary.create(
    ContextSourceType.SESSION,
    target_units=2_000,
    preserve_recent_messages=8,
)
~~~

Runtime selects the eligible source material, invokes the model through an internal instrumented capability, creates typed lineage and stages the transformation for final materialization.

Concrete Managers never receive the raw messages selected for summarization.

## Safe source set

Semantic summary currently supports:

~~~text
SESSION
CHECKPOINT
MEMORY
KNOWLEDGE
ARTIFACT
~~~

The Runtime rejects unsupported source types even if a custom Manager attempts to call the primitive.

## Summary result

`ContextSummaryResult` contains:

~~~text
summary_ref
source
source_refs
source_hash
content
raw_units
materialized_units
preserve_recent_messages
model_invocation_id
provider
model
~~~

The source hash covers the raw referenced source material. Stored summaries can only be reused when those references still exist and the content hash matches.

## Applying cached summary

`ctx.summary.apply(summary)` replaces exactly the historical source refs represented by that summary. Newly appended Session history is not accidentally swallowed.

This allows a checkpointed summary to be reused across later Model Invocations in the same Run.

## Incremental refresh

`await ctx.summary.refresh(summary, ...)` does not re-send the whole raw history.

~~~text
previous summary
      +
new eligible historical messages
      │
      ▼
summary model
      │
      ▼
refreshed summary
~~~

The refreshed result updates `source_refs` and `source_hash` to represent the full summarized set, while the model input contains the previous compressed summary plus only newly eligible history.

## Adaptive strategies

`AdaptiveContextManager` supports:

- `pressure_triggered`: create/refresh when candidate units relative to usable input budget reach `trigger_at`;
- `rolling`: create when enough eligible history exists, then refresh after `refresh_after_messages` additional candidates;
- `disabled`: never call the summary model.

`failure_mode=fallback_to_selection` preserves deterministic selection if summary generation fails. `failure_mode=fail` propagates the failure.

## Model invocation and observability

Summary currently uses the model object of the Model Invocation being prepared. The summary call bypasses Context assembly to prevent recursive summarization.

It is recorded in the same execution observability stream with:

~~~text
purpose = context_summary
phase = context_summary
unique call_id/model_invocation_id
parent invocation/call reference
input/output/total tokens
cost/status/latency
provider/model
~~~

Summary text is internal context work and is not streamed as the assistant's answer.

## Checkpointing

Adaptive stores a newly generated/refreshed summary in `ctx.state`, increments `summary_generation`, then awaits `ctx.checkpoint(ContextCheckpointBoundary.SUMMARY)`.

This makes summary reuse durable without treating the summary boundary as an Execution Tool checkpoint.

## Transformation evidence

When materialized, the summary keeps its original source type and records:

~~~text
selection_method = semantic_summary
transformations = [semantic_summary]
summary_source_refs
summary_source_hash
summary_model_invocation_id
summary_provider
summary_model
raw_units
materialized_units
~~~

Summary is therefore inspectable as a transformation rather than unexplained replacement text.

## Summary versus Memory

Summary compresses already-selected historical context. Memory is a reusable knowledge source with its own retrieval/persistence semantics.

A future product may persist a rolling summary into Session/Checkpoint/Memory storage, but that is an explicit persistence decision, not an implicit consequence of semantic summary.
