# SDK primitives

The Manager-facing surface is intentionally small and typed:

~~~text
ctx.policy
ctx.state
ctx.capacity
ctx.inventory
ctx.invocation
ctx.candidates
ctx.priorities
ctx.budget
ctx.pressure
ctx.sources
ctx.summary
ctx.has_active_skills
await ctx.checkpoint(...)
ctx.complete()
~~~

## `ctx.policy`

Read-only configured policy view by contract. Runtime keeps the effective mutable copy separate.

## `ctx.state`

Typed state declared by the concrete Manager's `state_type`.

~~~python
class MyState(ContextManagerState):
    iteration: int = 0
~~~

State should contain only serializable algorithm data. Do not put provider clients, messages or repositories into state.

## `ctx.capacity`

Read-only invocation capacity:

~~~text
model_capacity_units
reserved_output_units
runtime_reserve_units
configured_input_budget_units
model_usable_input_units
usable_input_budget_units
budget_clamped
~~~

Use this for primary/fallback-aware algorithms instead of hard-coding model names.

## `ctx.inventory`

Aggregate pre-selection facts without raw messages:

~~~python
ctx.inventory.total_count
ctx.inventory.total_units
ctx.inventory.sources
ctx.inventory.count(ContextSourceType.SESSION)
ctx.inventory.units(ContextSourceType.KNOWLEDGE)
ctx.inventory.contains(ContextSourceType.SKILL)
~~~

Inventory shares the assembler's source-classification logic and includes External Context, active Tool definitions and aggregate active Skill contribution units.

## `ctx.invocation`

Read-only invocation metadata:

~~~text
phase
provider
model
delegated
has_active_tools
~~~

This is deliberately narrower than `ContextAssemblyRequest`.

## `ctx.candidates`

Deterministic selection controls:

- `allow(sources)`;
- `recent_session(max_messages, max_units)`;
- `cap(source, max_units)`;
- `require(source, priority=MANDATORY)`;
- `deduplicate(strategy, sources)`;
- `order(strategy)`.

## `ctx.priorities`

`set(source, priority)` and `configure(mapping)` affect source-priority ordering, global overflow precedence and evidence. SYSTEM/USER_INPUT cannot be downgraded.

## `ctx.budget`

`configure(max_input_units, runtime_reserve_units)` programs configured input budget. Runtime still enforces invocation-specific model capacity/output reserve.

## `ctx.pressure`

`thresholds(moderate_at, high_at, critical_at)` changes pressure classification. It does not itself summarize or trim.

## `ctx.sources`

Enables reusable runtime-owned source materializers. Current built-in primitive: `ctx.sources.skills()`.

## `ctx.summary`

Semantic-summary capability executed and instrumented by Runtime.

~~~python
selection = ctx.summary.inspect(
    ContextSourceType.SESSION,
    preserve_recent_messages=8,
)

summary = await ctx.summary.create(
    ContextSourceType.SESSION,
    target_units=2_000,
    preserve_recent_messages=8,
)

refreshed = await ctx.summary.refresh(
    summary,
    target_units=2_000,
)

ctx.summary.apply(summary)
~~~

`inspect` exposes refs/hash/count/units, not raw message bodies.

`create` summarizes eligible historical material.

`refresh` is incremental: it sends the previous summary plus only newly eligible history to the summary model, while updating lineage to represent the complete summarized source set.

`apply` reuses a stored summary only if referenced source messages are still available and their hash matches.

Summary model calls are recorded in the execution trace with `purpose=context_summary` and `phase=context_summary`; they are not streamed as assistant output.

## `await ctx.checkpoint(...)`

Durably records Manager state at an algorithm boundary:

~~~python
await ctx.checkpoint(ContextCheckpointBoundary.SUMMARY)
~~~

Runtime immediately updates run-local hot Context state and emits durable `context.checkpoint` evidence. Recovery merges the newest Context state with a safe execution continuation without treating Context state as a Tool-causality checkpoint.

## `ctx.complete()`

Freezes/validates the effective policy into `ContextManagerOutcome`. The runner then performs summary materialization, Skills materialization and the shared deterministic context assembly.

## Deliberately absent

Managers do not receive raw messages, provider clients, persistence repositories or arbitrary Tool execution. New side-effecting capabilities should be added as explicit Runtime primitives rather than leaked through the context object.
