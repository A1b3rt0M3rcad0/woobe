# Creating a Context Manager

A normal built-in Manager should be small.

```text
1. create one file
2. implement assemble(ctx)
3. select/cap/order sources
4. configure budget behavior
5. complete
6. register in resolver
7. register in product catalog
8. test
```

## 1. Create one file

Create the Manager directly under:

```text
infra/context_management/managers/<name>.py
```

Do not create a package per Manager. The normal rule is:

```text
one Manager = one Python file
```

## 2. Implement assemble(ctx)

```python
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
```

Concrete Managers consume only the Context Manager SDK. They should not receive `ContextAssemblyRequest` or manipulate provider message classes.

## 3. Program the context algorithm

Example:

```python
def assemble(self, ctx):
    policy = ctx.policy

    ctx.candidates.allow(policy.allowed_sources)

    ctx.candidates.recent_session(
        max_messages=12,
        max_units=8_000,
    )

    ctx.candidates.cap(
        ContextSourceType.TOOL,
        6_000,
    )

    ctx.candidates.deduplicate(
        strategy="content_hash",
        sources=[
            ContextSourceType.TOOL,
            ContextSourceType.KNOWLEDGE,
        ],
    )

    ctx.candidates.order(
        strategy="source_priority",
    )

    ctx.budget.configure(
        max_input_units=48_000,
        runtime_reserve_units=4_000,
    )

    return ctx.complete()
```

The Manager describes decisions. The Runtime performs the actual safe materialization.

## 4. Optional runtime sources

The Standard Manager enables Skills only when the Run has active Skills:

```python
if ctx.has_active_skills:
    ctx.sources.skills()
```

A source capability must be implemented once in `manager_runtime/`, not duplicated inside each Manager.

## 5. Register runtime implementation

Add the factory explicitly in:

```text
infra/context_management/managers/resolver.py
```

Example:

```python
_BUILTIN_CONTEXT_MANAGER_FACTORIES = {
    StandardContextManager.name: StandardContextManager,
    AdaptiveContextManager.name: AdaptiveContextManager,
}
```

## 6. Register product metadata

Add one descriptor to the application Context Manager catalog.

The resolver answers **what implementation runs**. The catalog answers **how the product describes it**.

## 7. Tests

At minimum test:

- Manager algorithm decisions;
- resolver/catalog parity;
- budget behavior;
- Context Snapshot contributions;
- optional source materialization;
- legacy selection compatibility when relevant.

Adding a normal Manager should not require changes to `manager_runtime/`.
