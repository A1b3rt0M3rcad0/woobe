# Creating a new Execution Strategy

Use [`../standard.py`](../standard.py) as the minimal implementation reference and [`../scientific_method.py`](../scientific_method.py) when the new Strategy needs multiple semantic phases, invocation-local Directives, or recovery across repeated Tool-backed experiments.

The normal workflow is deliberately small:

```text
1. create one file
2. define State if needed
3. define Policy if needed
4. write execute(ctx)
5. register in resolver
6. register in catalog
7. test
```

## 1. Create one Strategy file

Create the Strategy directly under `infra/execution/strategies/`.

Example:

```text
packages/woobe-core/src/modules/agent/infra/execution/strategies/planner.py
```

Do not create a package such as:

```text
strategies/planner/
├── state.py
├── policy.py
├── phases.py
└── strategy.py
```

The design rule is:

```text
one Strategy = one Python file
```

A Strategy file may contain its local Phase enum, StopReason enum, State, Policy and algorithm implementation.

Start from the shared contracts you actually need:

```python
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategy
from modules.agent.application.strategy_sdk import (
    Completed,
    ExecutionPhase,
    ExecutionPolicy,
    ExecutionState,
    ExecutionStopReason,
    StrategyContext,
    StrategyOutputMode,
    StrategyOutcome,
)
```

The Standard file follows this shape:

```python
class StandardPhase(ExecutionPhase):
    ...

class StandardStopReason(ExecutionStopReason):
    ...

class StandardExecutionState(ExecutionState):
    ...

class StandardExecutionPolicy(
    ExecutionPolicy[StandardExecutionState]
):
    ...

class StandardExecutionStrategy(
    ExecutionStrategy[StandardExecutionState]
):
    ...
```

## 2. Define State only if the algorithm needs it

State contains only information the algorithm needs to remember between decisions and durable checkpoints.

The Standard example is intentionally small:

```python
class StandardExecutionState(ExecutionState):
    phase: str | None = None
    tool_round: int = 0
    consecutive_failures: int = 0
    stop_reason: StandardStopReason | None = None
```

Do not place messages, call indexes, recovery cursors or runtime services in State.

See [Execution State](./state.md) for the complete rules.

## 3. Define Policy only if the algorithm needs it

Policy is optional. Use it for deterministic algorithm limits or stop rules.

The Standard Policy evaluates the current State and returns a stop reason or `None`.

```python
reason = self.policy.stop_reason(state)
```

Do not create Policy just to move arbitrary orchestration out of `execute()`.

See [Execution Policy](./policy.md).

## 4. Implement `execute(ctx)`

A concrete Strategy implements:

```python
class PlannerExecutionStrategy(
    ExecutionStrategy[PlannerExecutionState]
):
    name = "planner"
    state_type = PlannerExecutionState

    async def execute(
        self,
        ctx: StrategyContext[PlannerExecutionState],
    ) -> StrategyOutcome:
        ...
```

The normal Strategy-facing surface is:

```text
ctx.state
ctx.model
ctx.tools
await ctx.checkpoint()
```

### Invoke the Model

```python
result = await ctx.model.invoke(
    phase=PlannerPhase.PLANNING,
)
```

The Runtime owns the current conversation and call instrumentation.

### Direct Model behavior for a Phase

A Phase identifies **where the algorithm is**. An optional Directive describes **how the Model should operate for that invocation**.

```python
result = await ctx.model.invoke(
    phase=PlannerPhase.REFLECT,
    directive=(
        "Evaluate the evidence collected so far, identify contradictions "
        "and determine whether additional actions are required."
    ),
)
```

Directive semantics are intentionally narrow:

```text
Phase       = stable semantic identity of an execution step
Directive   = ephemeral behavior instruction for one Model invocation
```

A Directive does not mutate or replace Agent Behavior, objective, Skills, Session state or persistent context. The Strategy supplies it again on a later invocation if the same behavior is still required.

Use Directives for execution behavior such as planning, reflection, verification or synthesis. Do not use them as a transport for dynamic business payloads, Tool results, customer data or large context. Those values belong to the normal context pipeline.

### Declare public output ownership

For new multi-phase Strategies, do not rely on a phase-name convention to decide which invocation may stream the assistant answer.

```python
result = await ctx.model.invoke(
    phase=PlannerPhase.SYNTHESIS,
    directive="Produce the final answer from the validated plan.",
    output_mode=StrategyOutputMode.FINAL,
)
```

Internal planning or reasoning invocations should use `StrategyOutputMode.INTERNAL`. Use `StrategyOutputMode.INTERMEDIATE` when the Agent should send a real Assistant message and then continue executing, and `StrategyOutputMode.FINAL` for the terminal response. Existing Strategies can omit the argument and keep the historical runtime behavior. The frontend consumes runtime message identity and does not maintain a list of Strategy-specific final phases.

### Execute Tools

```python
if result.has_tool_calls:
    batch = await ctx.tools.execute_many(
        result.tool_calls,
    )
```

The Runtime records Tool evidence and updates Model/Tool conversation progression automatically.

The Strategy may inspect normalized batch data when it affects the algorithm:

```python
if batch.has_failures:
    ctx.state.consecutive_failures += 1
```

### Checkpoint durable progress

```python
await ctx.checkpoint()
```

Checkpoint after an algorithm boundary when a restart must resume from the updated State without replaying completed side effects.

The Strategy does not serialize State or construct a recovery cursor.

### Complete the Strategy

```python
return Completed(result)
```

Do not mutate `InstrumentedExecution` directly.

### Standard algorithm shape

The Standard implementation is approximately:

```python
state = ctx.state
result = await ctx.model.invoke(phase=state.phase)

while result.has_tool_calls and state.tool_round < self.policy.max_tool_rounds:
    batch = await ctx.tools.execute_many(result.tool_calls)

    state.tool_round += 1
    state.stop_reason = self.policy.stop_reason(state)

    await ctx.checkpoint()

    if state.stop_reason is not None:
        break

    result = await ctx.model.invoke(phase=state.phase)

return Completed(result)
```

Read the real [`standard.py`](../standard.py) for the authoritative behavior, including failure counters, finalization and current suspension handling.

## 5. Register the Strategy in the resolver

Add the concrete implementation to [`../resolver.py`](../resolver.py).

Current Standard registration:

```python
_BUILTIN_EXECUTION_STRATEGY_FACTORIES = {
    StandardExecutionStrategy.name: StandardExecutionStrategy,
}
```

With Planner:

```python
_BUILTIN_EXECUTION_STRATEGY_FACTORIES = {
    StandardExecutionStrategy.name: StandardExecutionStrategy,
    PlannerExecutionStrategy.name: PlannerExecutionStrategy,
}
```

Keep registration explicit. Do not add auto-discovery or decorator-based registration for built-in Strategies.

Names must be stable and unversioned:

```text
standard
planner
react
```

Do not introduce `standard:v1` or similar identities.

## 6. Register product metadata in the catalog

Add a descriptor to:

```text
packages/woobe-core/src/modules/agent/application/execution_strategy_registry.py
```

The resolver answers **what implementation runs**. The catalog answers **how the product describes the Strategy**.

The descriptor should include:

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

Use the existing `_STANDARD_DESCRIPTOR` as the reference.

A normal new Strategy should use:

```python
is_default=False
```

`standard` remains the historical fallback unless changing that behavior is explicitly part of another change.

See [Resolver and product catalog](./resolver-and-catalog.md).

## 7. Add tests

At minimum, add behavior tests for what makes the Strategy different.

If it checkpoints durable progress, add recovery tests that prove completed Tool side effects are not replayed after restart.

Also keep runtime resolver and product catalog names in parity.

See [Testing and validation](./testing.md).

## Quick checklist

A normal Strategy addition should result in approximately:

```text
new:    infra/execution/strategies/<name>.py
edit:   infra/execution/strategies/resolver.py
edit:   application/execution_strategy_registry.py
new:    tests/unit/agent/test_<name>_execution_strategy.py
```

It should normally **not** require changes to `strategy_runtime/`.


## Choosing the right reference

Use `standard.py` when the new algorithm is primarily a Model/Tool loop with deterministic limits.

Use `scientific_method.py` when the algorithm itself owns a sequence of cognitive phases. It demonstrates the intended pattern for:

- Strategy-specific `ExecutionPhase` values;
- a small serializable State machine;
- a real `ExecutionPolicy`;
- different Directives for different Model invocations;
- explicit public-output ownership for terminal versus internal phases;
- Tool calls as algorithmic experiments;
- checkpointing after durable side effects;
- resume into the next semantic phase without replaying the Tool;
- normal completion versus conservative `finalize()` after a stop condition.

A Directive should be derived from the current phase and State. Do not persist the Directive itself. Persist only the algorithm information needed to reconstruct which Directive must be used after resume.
