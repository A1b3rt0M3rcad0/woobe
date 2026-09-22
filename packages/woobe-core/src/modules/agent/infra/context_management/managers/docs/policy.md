# Context Policy

`ContextPolicyV1` is the shared configuration contract supplied to each Context Manager. It is not the algorithm itself.

Different Managers may interpret a supported policy capability differently, but every effective mutation must still satisfy the same validated policy schema.

## Policy flow

~~~text
Agent runtime_config.context
        │
        ▼
ContextPolicyV1
        │
        ▼
ctx.policy  configured snapshot
        │
        ▼
Manager programs primitives
        │
        ▼
effective ContextPolicyV1
        │
        ▼
Context Manager Runtime
~~~

## Current policy mapping

| Policy field | Runtime/Manager semantics | Status |
| --- | --- | --- |
| `allowed_sources` | candidate source filtering | effective |
| `source_priorities` | ordering and global-overflow precedence | effective |
| `session.*` | recent Session window/count/unit cap | effective |
| `checkpoints.max_units` | CHECKPOINT source cap | effective |
| `memory.max_units` | MEMORY source cap | effective |
| `knowledge.max_units` | KNOWLEDGE source cap | effective |
| `tools.max_result_units` | TOOL source cap | effective |
| `artifacts.max_units` | ARTIFACT source cap | effective |
| `delegation.max_units` | DELEGATION source cap | effective |
| `budget.*` | configured budget, later clamped by model capacity | effective |
| `pressure.*` | LOW/MODERATE/HIGH/CRITICAL evidence thresholds | effective, diagnostic |
| `ordering.strategy` | preserve-input or source-priority ordering | effective |
| `deduplication.*` | deterministic content-hash deduplication | effective |
| `skills.*` | Skills catalog/activation/materialization budgets | effective, split ownership |
| `summary.*` | semantic-summary behavior used by Adaptive | effective for Adaptive |
| `retention.materialized_content` | Snapshot retention metadata | v1 constrained to references_only |
| `artifacts.strategy` | declared reference_first/materialize mode | schema ahead of runtime |

## Summary Policy

`ContextSummaryPolicy` is now an implemented policy contract:

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

`disabled` is the default, so upgrading an existing Agent does not add summary model calls.

`pressure_triggered` creates/refreshes summaries when candidate pressure reaches `trigger_at`.

`rolling` creates a summary when enough eligible material exists and refreshes after `refresh_after_messages` additional eligible candidates.

Supported summary sources today:

~~~text
SESSION
CHECKPOINT
MEMORY
KNOWLEDGE
ARTIFACT
~~~

SYSTEM and current USER_INPUT are mandatory and cannot be summarized. TOOL, DELEGATION, RUNTIME and SKILL are not currently accepted by semantic-summary Runtime because replacing them independently can violate execution/procedure semantics.

## Standard versus Adaptive policy behavior

Standard honors deterministic selection/budget policy and intentionally ignores semantic-summary execution even when `summary.strategy` is enabled.

Adaptive honors the same deterministic policy plus `summary.*`, capacity-aware source caps and optional summary/checkpoint behavior.

This separation lets product configuration select an algorithm without changing the policy schema.

## Mandatory invariants

`SYSTEM` and current `USER_INPUT` remain `MANDATORY`. SDK priorities reject attempts to downgrade them, and Runtime rejects effective policy that excludes mandatory current context.

## Policy mutation

Read `ctx.policy`; program effective behavior through primitives:

~~~python
ctx.priorities.set(ContextSourceType.KNOWLEDGE, ContextPriority.HIGH)
~~~

Do not rely on direct mutation of `ctx.policy`.

## Versioning

`ContextPolicyV1.schema_version` versions the policy schema. Manager identities remain stable and unversioned (`standard`, `adaptive`).
