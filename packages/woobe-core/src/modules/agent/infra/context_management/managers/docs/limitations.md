# Current limitations

The programmable Context Manager architecture now supports async algorithms, typed state, semantic summary and durable Context checkpoints. The remaining boundaries should stay explicit.

## Summary model selection

Semantic summary currently uses the model instance of the Model Invocation being prepared. There is no separate `summary_model` selection policy yet.

A dedicated cheaper summary model can be introduced later as a Runtime capability without changing concrete Manager access to providers.

## Run-local summary state

Adaptive checkpoints survive later Model Invocations and process recovery inside the same Run, but they are not automatically inherited by a new Run in the same Session.

Cross-Run long-horizon summaries need a Session Context Store, Memory integration or another explicit persisted source contract.

## Artifact strategy

`ArtifactContextPolicy.strategy` still exposes `reference_first` and `materialize`, but shared assembly does not yet execute distinct artifact-materialization paths. The artifact unit cap is effective; the strategy switch is still schema ahead of runtime.

## Retention

`ContextRetentionPolicy` v1 supports only `references_only` for Context Snapshot materialized-content retention.

## Pressure semantics

`ctx.pressure.thresholds(...)` changes Context health classification. It does not itself perform trimming or summary.

Adaptive separately uses `ContextSummaryPolicy.trigger_at` for pressure-triggered summary decisions.

## Retrieval remains upstream

Knowledge, Memory and Checkpoint retrieval algorithms are not owned by Context Manager today. Managers see aggregate candidate inventory and govern participation/caps after those candidates are available.

## Skills split ownership

Skills catalog/search/activation can happen earlier in the Run. `ctx.inventory` exposes aggregate active Skill units and `ctx.sources.skills()` controls invocation materialization, but a Context Manager does not own the whole Skills lifecycle.

## Raw context access

Concrete Managers intentionally do not receive raw message bodies. `ctx.inventory` exposes aggregate counts/units and `ctx.summary` provides a controlled semantic transformation.

If another algorithm needs semantic inspection without summarization, add a purpose-built Runtime primitive instead of leaking provider messages.

## Outer compatibility bridge

The official `ContextAssembler` contract is asynchronous. Execution instrumentation temporarily accepts a synchronous outer assembler result through an awaitable compatibility bridge so existing custom/test replacements do not fail immediately. Built-in Context Managers are async and should not rely on that bridge.

## Safe summary source set

TOOL is not semantically summarized because removing Tool messages independently can break assistant Tool-call pairing. Current input and SYSTEM are mandatory. DELEGATION, RUNTIME and SKILL also remain outside semantic-summary replacement until their semantics are explicitly defined.
