# SDK primitives

The stable Manager-facing surface is:

~~~text
ctx.policy
ctx.candidates
ctx.capacity
ctx.inventory
ctx.priorities
ctx.budget
ctx.pressure
ctx.sources
ctx.has_active_skills
ctx.complete()
~~~

`ctx.policy` is configured input. The remaining members are the supported programming surface.

## `ctx.candidates`

Controls candidate eligibility and deterministic selection:

- `allow(sources)` replaces the allowed source set;
- `recent_session(max_messages, max_units)` selects recent Session context;
- `cap(source, max_units)` applies a per-source cap where supported;
- `require(source, priority=MANDATORY)` allows a source and assigns priority;
- `deduplicate(strategy, sources)` configures duplicate elimination;
- `order(strategy)` configures final ordering.

`cap(...)` currently supports CHECKPOINT, MEMORY, KNOWLEDGE, TOOL, ARTIFACT and DELEGATION. Session has its own window primitive. SYSTEM and current USER_INPUT are mandatory invariants.

## `ctx.capacity`

Provides read-only invocation capacity facts without exposing provider/runtime objects:

~~~python
ctx.capacity.model_capacity_units
ctx.capacity.reserved_output_units
ctx.capacity.runtime_reserve_units
ctx.capacity.configured_input_budget_units
ctx.capacity.model_usable_input_units
ctx.capacity.usable_input_budget_units
ctx.capacity.budget_clamped
~~~

The values track the effective Manager budget. If the Manager calls `ctx.budget.configure(...)`, subsequent capacity reads reflect the new configured budget/reserve.

This lets adaptive Managers react differently to a large primary model and a smaller fallback model without bypassing Runtime capacity enforcement.

## `ctx.inventory`

Provides aggregate pre-selection facts by `ContextSourceType`:

~~~python
ctx.inventory.total_count
ctx.inventory.total_units
ctx.inventory.sources
ctx.inventory.count(ContextSourceType.SESSION)
ctx.inventory.units(ContextSourceType.KNOWLEDGE)
ctx.inventory.contains(ContextSourceType.TOOL)
~~~

Managers do not receive raw messages. Inventory uses the same source-classification logic as the assembler, includes contract-exposed External Context and active Tool definitions, and is calculated before optional Manager-enabled materializers such as active Skills are inserted.

## `ctx.priorities`

Controls source priority independently from source eligibility:

~~~python
ctx.priorities.set(
    ContextSourceType.KNOWLEDGE,
    ContextPriority.HIGH,
)
ctx.priorities.configure(policy.source_priorities)
~~~

Priorities affect source-priority ordering, global overflow precedence and persisted contribution evidence.

SYSTEM and USER_INPUT cannot be downgraded from MANDATORY.

## `ctx.budget`

~~~python
ctx.budget.configure(
    max_input_units=48_000,
    runtime_reserve_units=4_000,
)
~~~

Runtime still clamps against invocation-specific model capacity and output reserve. A Manager cannot force materialization beyond the usable model window.

## `ctx.pressure`

~~~python
ctx.pressure.thresholds(
    moderate_at=0.40,
    high_at=0.75,
    critical_at=0.90,
)
~~~

These thresholds classify Context health/evidence. They do not trigger a separate adaptive algorithm.

## `ctx.sources`

Enables optional runtime-owned materialization.

Current shared primitive:

~~~python
if ctx.has_active_skills:
    ctx.sources.skills()
~~~

Runtime owns Skill message construction, budget validation, provenance and manifest enrichment.

External Context is runtime-owned but contract-authorized rather than an optional Manager materializer, so it is not toggled through `ctx.sources`.

## `ctx.complete()`

`ctx.complete()` freezes the effective algorithm decisions into `ContextManagerOutcome`. The runner validates the outcome before materialization.

## Deliberately absent primitives

The SDK does not currently expose semantic summary, model-based compression, artifact reference/materialize switching, custom retention modes, custom retrieval, or provider-specific message construction.

Some are upstream source-production concerns; others require Runtime capabilities that do not exist yet. See [Summary and compaction](./summary-and-compaction.md) and [Current limitations](./limitations.md).
