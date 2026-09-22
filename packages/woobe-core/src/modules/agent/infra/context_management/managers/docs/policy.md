# Context Policy

`ContextPolicyV1` is the configuration contract supplied to a Context Manager for one Model Invocation. It is **not** the Manager algorithm.

The policy says what the Agent is configured to prefer or limit. The Manager expresses those settings through SDK primitives, and Runtime enforces the resulting effective policy.

## Policy flow

~~~text
Agent runtime_config.context
        │
        ▼
ContextPolicyV1
        │
        ▼
ctx.policy  (configured snapshot)
        │
        ▼
Manager programs SDK primitives
        │
        ▼
effective ContextPolicyV1
        │
        ▼
Context Manager Runtime
~~~

## Current field-to-primitive mapping

| Policy field | Standard primitive | Runtime effect | Status |
| --- | --- | --- | --- |
| `allowed_sources` | `ctx.candidates.allow(...)` | source filtering | effective |
| `source_priorities` | `ctx.priorities.configure(...)` | ordering and overflow precedence | effective |
| `session.strategy=recent` | `ctx.candidates.recent_session(...)` | recent Session window | effective |
| `session.max_messages` | `ctx.candidates.recent_session(...)` | Session count limit | effective |
| `session.max_units` | `ctx.candidates.recent_session(...)` | Session unit cap | effective |
| `checkpoints.max_units` | `ctx.candidates.cap(CHECKPOINT, ...)` | source cap | effective |
| `memory.max_units` | `ctx.candidates.cap(MEMORY, ...)` | source cap | effective |
| `knowledge.max_units` | `ctx.candidates.cap(KNOWLEDGE, ...)` | source cap | effective |
| `tools.max_result_units` | `ctx.candidates.cap(TOOL, ...)` | source cap | effective |
| `artifacts.max_units` | `ctx.candidates.cap(ARTIFACT, ...)` | source cap | effective |
| `delegation.max_units` | `ctx.candidates.cap(DELEGATION, ...)` | source cap | effective |
| `budget.*` | `ctx.budget.configure(...)` | budget plus model-capacity clamp | effective |
| `pressure.*` | `ctx.pressure.thresholds(...)` | pressure classification/evidence | effective, diagnostic |
| `ordering.strategy` | `ctx.candidates.order(...)` | final materialized order | effective |
| `deduplication.*` | `ctx.candidates.deduplicate(...)` | duplicate removal | effective |
| `skills.*` | Skills runtime + `ctx.sources.skills()` | Skill budgets/materialization | effective, split ownership |
| `retention.materialized_content` | no Manager primitive | Snapshot retention metadata | v1 constrained |
| `artifacts.strategy` | no Manager primitive | no differentiated runtime behavior today | declarative/incomplete |

## Mandatory invariants

`SYSTEM` and current `USER_INPUT` priorities must remain `MANDATORY`. The priority primitive rejects attempts to downgrade them.

Runtime also rejects effective policies that exclude mandatory current context.

## Why Managers should not mutate `ctx.policy`

Direct mutation would create an undocumented second programming surface. Runtime therefore isolates configured policy from effective policy.

Use:

~~~python
ctx.priorities.set(ContextSourceType.KNOWLEDGE, ContextPriority.HIGH)
~~~

not:

~~~python
ctx.policy.source_priorities[ContextSourceType.KNOWLEDGE] = ContextPriority.HIGH
~~~

## Versioning

`ContextPolicyV1.schema_version` versions the policy schema. Context Manager identities themselves remain unversioned (`standard`, `adaptive`, etc.).

A breaking policy change should introduce a new policy schema version rather than encoding policy versions into Manager names.
