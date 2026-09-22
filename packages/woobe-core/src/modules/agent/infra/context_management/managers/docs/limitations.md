# Current limitations

This document is intentionally explicit about what the Context Manager abstraction does and does not support today.

## Semantic summary: not implemented

No built-in Runtime primitive performs model-based summarization. See [Summary and compaction](./summary-and-compaction.md).

## Artifact strategy: schema ahead of runtime

`ArtifactContextPolicy.strategy` exposes `reference_first` and `materialize`, but `context_assembly.py` does not currently execute different artifact materialization paths based on that field.

The Standard Manager therefore programs only the artifact unit cap. Do not advertise artifact strategy as a working programmable primitive until Runtime has concrete semantics for both strategies.

## Retention: v1 is references-only

`ContextRetentionPolicy` currently validates only `references_only`. The value is persisted into Context Snapshot metadata.

`REDACTED` and `FULL` exist in the domain enum but are not supported `ContextPolicyV1` behaviors.

## Pressure thresholds are diagnostic

`ctx.pressure.thresholds(...)` controls LOW/MODERATE/HIGH/CRITICAL classification. It does not automatically switch algorithms or summarize context.

## Retrieval remains upstream

Knowledge, Memory and Checkpoint policy currently controls participation/caps after contributions exist. Context Manager does not own the retrieval algorithm that produced them.

Semantic search, memory ranking or checkpoint lookup should become explicit source-production capabilities rather than hidden behavior inside candidate selection.

## Skills policy has split ownership

`SkillContextPolicy` configures Skills catalog/search/activation budgets before and during execution. `ctx.sources.skills()` only opts active Skill contributions into invocation materialization.

A Context Manager cannot safely reconfigure every Skills field at assembly time because some Skills decisions happen earlier in the Run.

## Synchronous assembly boundary

`ContextAssembler.assemble()` is synchronous. Future primitives requiring I/O must introduce an explicit async Runtime boundary instead of blocking inside a Manager.

## Inventory is aggregate, not raw context access

`ctx.inventory` intentionally exposes counts and estimated units by source, not message bodies.

It is computed from the same base candidate classification used by assembly, including contract-exposed External Context and active Tool definitions. Optional Manager-enabled sources such as active Skill materialization occur after the Manager decision and therefore are represented separately through runtime-specific facts such as `ctx.has_active_skills`.

If a future algorithm genuinely needs semantic inspection of candidate content, that should become a purpose-built Runtime primitive rather than exposing raw LangChain messages to concrete Managers.
