# Creating a Context Manager

Use [`../standard.py`](../standard.py) as the canonical implementation reference.

The normal workflow is:

~~~text
1. create one Manager file
2. read configured policy
3. program SDK primitives
4. complete the outcome
5. register in resolver
6. register in product catalog
7. add behavior/extensibility tests
8. run architecture gates
~~~

## 1. Create one file

Create the Manager directly under:

~~~text
packages/woobe-core/src/modules/agent/infra/context_management/managers/<name>.py
~~~

The normal rule is:

~~~text
one Manager = one Python file
~~~

Do not create a Manager-specific package for selector/policy/runtime helpers unless the platform architecture itself changes.

## 2. Implement `assemble(ctx)`

~~~python
from modules.agent.application.context_manager_sdk import (
    ContextManagerContext,
    ContextManagerOutcome,
)


class AdaptiveContextManager:
    name = "adaptive"

    def assemble(
        self,
        ctx: ContextManagerContext,
    ) -> ContextManagerOutcome:
        ...
        return ctx.complete()
~~~

Concrete Managers consume only the Context Manager SDK plus stable Domain enums/value types.

Do not receive `ContextAssemblyRequest`, construct provider messages, or build `ContextSnapshot` directly.

## 3. Read configured policy

~~~python
policy = ctx.policy
~~~

`ctx.policy` is configured input and is isolated from effective behavior.

Do not attempt to program behavior by mutating it directly.

## 4. Program candidates

~~~python
ctx.candidates.allow(policy.allowed_sources)
ctx.candidates.recent_session(
    max_messages=8,
    max_units=4_000,
)
ctx.candidates.cap(ContextSourceType.TOOL, 2_000)
ctx.candidates.deduplicate(
    strategy="content_hash",
    sources=[ContextSourceType.SESSION, ContextSourceType.TOOL],
)
ctx.candidates.order(strategy="source_priority")
~~~

## 5. Program priorities

~~~python
ctx.priorities.set(
    ContextSourceType.KNOWLEDGE,
    ContextPriority.HIGH,
)
~~~

Priorities influence source-priority ordering, global overflow precedence and evidence.

SYSTEM and current USER_INPUT remain MANDATORY.

## 6. Program budget

~~~python
ctx.budget.configure(
    max_input_units=32_000,
    runtime_reserve_units=2_000,
)
~~~

Runtime still clamps against actual model capacity and output reserve.

## 7. Configure pressure evidence

~~~python
ctx.pressure.thresholds(
    moderate_at=0.40,
    high_at=0.75,
    critical_at=0.90,
)
~~~

These are classification thresholds, not automatic adaptive actions.

## 8. Enable optional runtime sources

~~~python
if ctx.has_active_skills:
    ctx.sources.skills()
~~~

Do not duplicate Skills or External Context construction inside a Manager.

## 9. Complete

~~~python
return ctx.complete()
~~~

`ContextManagerRunner` validates the outcome and executes shared materialization mechanics.

## Complete example

~~~python
class KnowledgeFirstContextManager:
    name = "knowledge-first"

    def assemble(self, ctx: ContextManagerContext) -> ContextManagerOutcome:
        policy = ctx.policy

        ctx.candidates.allow(policy.allowed_sources)
        ctx.priorities.configure(policy.source_priorities)
        ctx.priorities.set(ContextSourceType.KNOWLEDGE, ContextPriority.HIGH)

        ctx.candidates.recent_session(max_messages=6, max_units=3_000)
        ctx.candidates.cap(ContextSourceType.KNOWLEDGE, 12_000)
        ctx.candidates.cap(ContextSourceType.TOOL, 2_000)
        ctx.candidates.order(strategy="source_priority")
        ctx.candidates.deduplicate(
            strategy="content_hash",
            sources=[ContextSourceType.SESSION, ContextSourceType.KNOWLEDGE],
        )

        ctx.budget.configure(
            max_input_units=policy.budget.max_input_units,
            runtime_reserve_units=policy.budget.runtime_reserve_units,
        )
        ctx.pressure.thresholds(
            moderate_at=policy.pressure.moderate_at,
            high_at=policy.pressure.high_at,
            critical_at=policy.pressure.critical_at,
        )

        if ctx.has_active_skills:
            ctx.sources.skills()

        return ctx.complete()
~~~

## 10. Register runtime implementation

Add the class to `infra/context_management/managers/resolver.py`:

~~~python
_BUILTIN_CONTEXT_MANAGER_FACTORIES = {
    StandardContextManager.name: StandardContextManager,
    KnowledgeFirstContextManager.name: KnowledgeFirstContextManager,
}
~~~

Keep registration explicit. Names must be stable, lowercase and unversioned.

## 11. Register product metadata

Add a descriptor to `application/context_manager_registry.py`.

The resolver answers **what implementation runs**. The catalog answers **how the product describes it**.

## 12. Test

At minimum test algorithm decisions, policy isolation, resolver/catalog parity, budget behavior, priority behavior, Snapshot evidence, optional source materialization and relevant legacy compatibility.

If the Manager seems to need semantic summary, read [Summary and compaction](./summary-and-compaction.md) before adding any new primitive.
