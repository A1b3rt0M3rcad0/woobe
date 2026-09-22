# Creating a Context Manager

Use `standard.py` for the minimal deterministic implementation and `adaptive.py` for state/summary/checkpoint patterns.

## 1. One Manager, one file

Create:

~~~text
packages/woobe-core/src/modules/agent/infra/context_management/managers/<name>.py
~~~

Normal Managers should not create their own runtime packages.

## 2. Declare state and async `assemble(ctx)`

Every Manager declares `state_type` and implements the async contract:

~~~python
from modules.agent.application.context_manager_sdk import (
    ContextManagerContext,
    ContextManagerOutcome,
    ContextManagerState,
)

class MyContextState(ContextManagerState):
    decision_count: int = 0

class MyContextManager:
    name = "my-manager"
    state_type = MyContextState

    async def assemble(
        self,
        ctx: ContextManagerContext[MyContextState],
    ) -> ContextManagerOutcome:
        ...
        return ctx.complete()
~~~

Use the empty `ContextManagerState` when no algorithm state is needed.

## 3. Read policy; do not mutate it

~~~python
policy = ctx.policy
~~~

Program effective behavior through SDK primitives. Direct mutation of `ctx.policy` is intentionally isolated from the effective policy.

## 4. Inspect algorithm facts

~~~python
usable = ctx.capacity.usable_input_budget_units
session_units = ctx.inventory.units(ContextSourceType.SESSION)
phase = ctx.invocation.phase
~~~

These views are read-only and do not expose outer runtime objects.

## 5. Program deterministic selection

~~~python
ctx.candidates.allow(policy.allowed_sources)
ctx.priorities.configure(policy.source_priorities)
ctx.candidates.recent_session(max_messages=8, max_units=4_000)
ctx.candidates.cap(ContextSourceType.KNOWLEDGE, 12_000)
ctx.candidates.deduplicate(
    strategy="content_hash",
    sources=[ContextSourceType.SESSION, ContextSourceType.KNOWLEDGE],
)
ctx.candidates.order(strategy="source_priority")
ctx.budget.configure(
    max_input_units=policy.budget.max_input_units,
    runtime_reserve_units=policy.budget.runtime_reserve_units,
)
~~~

## 6. Use async Runtime capabilities when needed

Semantic summary:

~~~python
selection = ctx.summary.inspect(
    ContextSourceType.SESSION,
    preserve_recent_messages=8,
)

if selection.raw_units > 20_000:
    summary = await ctx.summary.create(
        ContextSourceType.SESSION,
        target_units=2_000,
        preserve_recent_messages=8,
    )
    ctx.state.last_summary = summary
    await ctx.checkpoint(ContextCheckpointBoundary.SUMMARY)
~~~

On a later invocation, reuse or incrementally refresh:

~~~python
ctx.summary.apply(ctx.state.last_summary)

refreshed = await ctx.summary.refresh(
    ctx.state.last_summary,
    target_units=2_000,
)
~~~

Do not call provider APIs or persistence repositories directly.

## 7. Optional runtime-owned sources

~~~python
if ctx.has_active_skills:
    ctx.sources.skills()
~~~

## 8. Complete

~~~python
return ctx.complete()
~~~

`ContextManagerRunner` validates the outcome, applies staged summary transformations, materializes optional sources and calls the shared deterministic assembler.

## Example: phase-aware compact Manager

~~~python
class CompactContextManager:
    name = "compact"
    state_type = ContextManagerState

    async def assemble(self, ctx):
        policy = ctx.policy
        ctx.candidates.allow(policy.allowed_sources)
        ctx.priorities.configure(policy.source_priorities)

        usable = ctx.capacity.usable_input_budget_units
        session_cap = None if usable is None else max(512, usable // 3)
        max_messages = 4 if ctx.invocation.phase == "json_repair" else 12

        ctx.candidates.recent_session(
            max_messages=max_messages,
            max_units=session_cap,
        )
        ctx.candidates.order(strategy="source_priority")
        return ctx.complete()
~~~

## 9. Register runtime implementation

Add it explicitly to `_BUILTIN_CONTEXT_MANAGER_FACTORIES` in `resolver.py`.

Do not use filesystem scanning, decorators or auto-discovery for built-ins.

## 10. Register product metadata

Add a descriptor in `application/context_manager_registry.py`. Resolver and catalog names must stay in parity.

## 11. Test the algorithm, not Runtime again

Test Manager-specific decisions, state evolution, summary/checkpoint triggers and failure policy. Shared Runtime mechanics belong in generic Runtime tests.

Use `tests/unit/agent/test_context_manager_programming.py` and `test_adaptive_context_manager.py` as references.
