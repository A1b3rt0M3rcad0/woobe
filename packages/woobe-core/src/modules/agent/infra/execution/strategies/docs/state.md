# Execution State

`ExecutionState` is the durable memory of a concrete execution algorithm.

It exists so the Strategy can resume its own decision process after a checkpoint without owning runtime persistence or recovery infrastructure.

## What belongs in State

Only values that influence future algorithm decisions.

Examples:

```text
tool_round
iteration
current_step
replan_count
stop_reason
selected_branch
algorithm-local observations
```

The Standard implementation stores only:

```python
class StandardExecutionState(ExecutionState):
    phase: str | None = None
    tool_round: int = 0
    consecutive_failures: int = 0
    stop_reason: StandardStopReason | None = None
```

Each field changes how the Standard algorithm resumes or decides what to do next.

## What must not be in State

Do not store runtime-owned data such as:

```text
messages
call_index
InstrumentedExecution
Model messages
Tool messages
provider clients
Tool executors
recovery cursor formats
checkpoint serializers
stream state
Run lifecycle state
persistence services
```

The Strategy Runtime already owns those concerns.

## No custom persistence contract

Concrete State must not implement infrastructure methods such as:

```text
create()
restore()
checkpoint_cursor()
checkpoint_messages()
record_model_result()
record_tool_batch()
```

The generic `RuntimeStrategyStateStore` serializes and restores `ExecutionState` automatically.

A State should therefore be a small, default-constructible model:

```python
class ReActExecutionState(ExecutionState):
    iteration: int = 0
```

A Planner may require more:

```python
class PlannerExecutionState(ExecutionState):
    current_step: int = 0
    replan_count: int = 0
    plan: list[str] = []
```

Only add those fields when they are real algorithm state.

## Practical rule

> If removing a field would not change a future algorithm decision, that field probably does not belong in concrete Strategy State.

## Serialization requirements

State data should be compatible with the shared serializable model used by `ExecutionState`. Prefer simple typed values and nested structures that can be validated and serialized predictably.

Typical values include:

```text
str
int
float
bool
None
lists
dicts
Strategy-specific enums
nested serializable models
```

Do not introduce a Strategy-specific State codec unless the shared contract genuinely cannot represent a required execution primitive. A normal Strategy must not need its own codec or factory.
