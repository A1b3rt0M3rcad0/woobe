# Resolver and product catalog

A built-in Execution Strategy must be registered in two places with different responsibilities.

## Runtime resolver

File:

```text
packages/woobe-core/src/modules/agent/infra/execution/strategies/resolver.py
```

The resolver maps a stable Strategy name to the concrete implementation that executes.

Current Standard registration:

```python
_BUILTIN_EXECUTION_STRATEGY_FACTORIES = {
    StandardExecutionStrategy.name: StandardExecutionStrategy,
}
```

Adding Planner would look like:

```python
_BUILTIN_EXECUTION_STRATEGY_FACTORIES = {
    StandardExecutionStrategy.name: StandardExecutionStrategy,
    PlannerExecutionStrategy.name: PlannerExecutionStrategy,
}
```

Registration should stay explicit.

Do not add auto-discovery, decorators or filesystem scanning for built-in Strategies.

## Product catalog

File:

```text
packages/woobe-core/src/modules/agent/application/execution_strategy_registry.py
```

The catalog describes the Strategy to API and product surfaces. It does not import or execute concrete Strategy classes.

The existing `_STANDARD_DESCRIPTOR` is the reference.

A descriptor includes:

```text
name
display_name
description
behavior
recommended_for
capabilities
limitations
is_default
```

A future descriptor may look like:

```python
_PLANNER_DESCRIPTOR = ExecutionStrategyDescriptor(
    name="planner",
    display_name="Planner",
    description="...",
    behavior="...",
    recommended_for=("...",),
    capabilities=("...",),
    limitations=("...",),
    is_default=False,
)
```

Then register it in `build_execution_strategy_registry()`.

## Resolver vs catalog

Keep the distinction clear:

```text
resolver.py
= which implementation runs

execution_strategy_registry.py
= how Woobe describes the Strategy as a product capability
```

The Application catalog must not depend on the concrete infrastructure implementation.

## Naming rules

Strategy names must be stable, lowercase and unversioned:

```text
standard
planner
react
reflection
```

Do not introduce identities such as:

```text
standard:v1
planner:v2
```

Release snapshots already preserve the selected runtime configuration. A second Strategy-version namespace would add unnecessary complexity.

## Parity requirement

Every selectable catalog Strategy must resolve at runtime, and every built-in runtime Strategy intended for selection must have corresponding product metadata.

The catalog/resolver tests enforce this parity.

`standard` remains the historical fallback and current default unless changing that behavior is an explicit product decision.
