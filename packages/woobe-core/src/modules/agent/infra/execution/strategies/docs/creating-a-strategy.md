# Creating a new Execution Strategy

Use [`../standard.py`](../standard.py) as the canonical implementation reference.

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
ctx.knowledge
ctx.context
ctx.model
ctx.tools
await ctx.checkpoint()
```

The runtime resolves and authorizes the underlying capabilities. The Strategy decides when to retrieve Knowledge, what Context contributions are active, which authorized Tools are visible to one Model invocation, and when the Model is invoked.

### Retrieve Knowledge when the algorithm needs it

Knowledge retrieval is an explicit Strategy decision:

```python
knowledge = await ctx.knowledge.retrieve(
    phase="knowledge_retrieval",
)

if knowledge.found:
    ctx.context.set(
        StrategyContextContribution(
            key="knowledge.primary",
            source_type="KNOWLEDGE",
            content=knowledge.content,
            metadata={"retrieval": dict(knowledge.metadata)},
        )
    )
```

Retrieving Knowledge and exposing it to the next Model invocation are separate decisions. The runtime owns the concrete Knowledge implementation and evidence; the Strategy owns the orchestration decision.

### Assemble Context and invoke the Model

Every Model invocation consumes an explicitly prepared invocation Context:

```python
tools = ctx.tools.all()

invocation = await ctx.context.assemble(
    phase=PlannerPhase.PLANNING,
    tools=tools,
)

result = await ctx.model.invoke(
    context=invocation,
    tools=tools,
    phase=PlannerPhase.PLANNING,
)
```

Use `ctx.tools.none()` for an invocation that must not expose Tools, or `ctx.tools.select("search", "lookup")` to expose only a subset of the Tools already authorized by the runtime.

The Runtime owns conversation progression, call instrumentation, Tool authorization and Context Manager implementation. The Strategy owns invocation order and per-invocation selection.

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

### Final Model invocation

A terminal response is also explicit. Build terminal Context with no Tools, then invoke the final Model:

```python
no_tools = ctx.tools.none()
invocation = await ctx.context.assemble_final(
    reason=state.stop_reason.value,
    phase=PlannerPhase.FINAL,
    tools=no_tools,
)

result = await ctx.model.finalize(
    reason=state.stop_reason.value,
    phase=PlannerPhase.FINAL,
    context=invocation,
    tools=no_tools,
)
```

`assemble_final(...)` preserves the normalized terminal prompt, successful and failed Tool evidence, structured-output instructions, Context contributions and the same Context budget policy used by ordinary invocations.

### Standard algorithm shape

The Standard implementation is approximately:

```python
state = ctx.state

if not state.knowledge_resolved:
    knowledge = await ctx.knowledge.retrieve(phase="knowledge_retrieval")
    state.knowledge_resolved = True
    if knowledge.found:
        ctx.context.set(
            StrategyContextContribution(
                key="knowledge.primary",
                source_type="KNOWLEDGE",
                content=knowledge.content,
            )
        )

tools = ctx.tools.all()
invocation = await ctx.context.assemble(
    phase=state.phase,
    tools=tools,
)
result = await ctx.model.invoke(
    context=invocation,
    tools=tools,
    phase=state.phase,
)

while result.has_tool_calls and state.tool_round < self.policy.max_tool_rounds:
    batch = await ctx.tools.execute_many(result.tool_calls)

    state.tool_round += 1
    state.stop_reason = self.policy.stop_reason(state)

    await ctx.checkpoint()

    if state.stop_reason is not None:
        break

    invocation = await ctx.context.assemble(
        phase=state.phase,
        tools=tools,
    )
    result = await ctx.model.invoke(
        context=invocation,
        tools=tools,
        phase=state.phase,
    )

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
