# Agent Execution Strategies

This directory is the extension point for concrete Agent execution algorithms.

The design rule is intentionally strict:

```text
one Strategy = one Python file
```

Examples:

```text
strategies/
├── resolver.py
├── standard.py
├── planner.py
├── react.py
└── reflection.py
```

A Strategy file may contain its own phase enum, stop-reason enum, small algorithm state, policy and algorithm. Those types stay together because they are one cohesive execution algorithm. Shared concepts belong to `application/strategy_sdk`.

The key boundary is that concrete Strategy state contains **algorithm data only**. Conversation messages, Model/Tool message progression, call indexes, instrumentation, checkpoint serialization and recovery restoration are owned by `infra/execution/strategy_runtime`.

A concrete Strategy receives `StrategyContext` and normally uses only:

```text
ctx.state
ctx.model
ctx.tools
await ctx.checkpoint()
```

Completion and suspension are explicit outcomes returned by the Strategy (`Completed(...)` / `Suspended(...)`) rather than lifecycle mutations on the context. The outer Strategy Runtime materializes those outcomes into runtime execution state.

`ExecutionState` is a serializable data model. A Strategy should only add fields the algorithm actually needs to remember between decisions, for example a tool round counter, a current plan step, a replan count or a stop reason. Do not add `messages`, recovery cursors, `create`/`restore` methods, checkpoint serializers or instrumentation fields to concrete state.

`ExecutionPolicy` is optional and should express algorithm limits or stop rules. Strategy-specific phases and stop reasons inherit the shared `ExecutionPhase` and `ExecutionStopReason` base enums. Iterated phase labels use the shared phase helper where compatibility requires them.

---

## Index

1. [Mental model](#mental-model)
2. [Files involved](#files-involved)
3. [What the Strategy Runtime already handles](#what-the-strategy-runtime-already-handles)
4. [Tutorial: creating a new Execution Strategy](#tutorial-creating-a-new-execution-strategy)
   1. [Create one Strategy file](#1-create-one-strategy-file)
   2. [Define State only if the algorithm needs it](#2-define-state-only-if-the-algorithm-needs-it)
   3. [Define Policy only if the algorithm needs it](#3-define-policy-only-if-the-algorithm-needs-it)
   4. [Implement execute(ctx)](#4-implement-executectx)
   5. [Register the Strategy in the resolver](#5-register-the-strategy-in-the-resolver)
   6. [Register product metadata in the catalog](#6-register-product-metadata-in-the-catalog)
   7. [Add tests](#7-add-tests)
5. [Standard as the reference implementation](#standard-as-the-reference-implementation)
6. [Rules for State](#rules-for-state)
7. [Rules for Policy](#rules-for-policy)
8. [Rules for phases and stop reasons](#rules-for-phases-and-stop-reasons)
9. [Architecture rules and forbidden dependencies](#architecture-rules-and-forbidden-dependencies)
10. [Validation checklist](#validation-checklist)
11. [When the Strategy Runtime should change](#when-the-strategy-runtime-should-change)
12. [Current limitation: suspension](#current-limitation-suspension)

---

## Mental model

An Execution Strategy is the algorithm that decides **how an Agent conducts model and capability execution**.

The Strategy owns decisions such as:

```text
invoke model
→ inspect result
→ execute Tools when needed
→ update algorithm state
→ decide whether to continue or stop
→ checkpoint durable progress
→ produce a final outcome
```

The Strategy does **not** own the Agent Run lifecycle or runtime infrastructure.

The intended dependency direction is:

```text
Concrete Strategy
      │
      ▼
StrategyContext
├── state
├── model
├── tools
└── checkpoint()
      │
      ▼
Strategy Runtime
├── conversation progression
├── state persistence
├── recovery
├── call indexes
├── instrumentation
└── runtime execution state
      │
      ▼
Execution Capabilities
├── Model invocation
└── Tool execution
```

A new Strategy should therefore mostly look like algorithm code, not runtime plumbing.

---

## Files involved

A normal built-in Strategy addition should touch only a small set of files.

### Concrete implementation

```text
packages/woobe-core/src/modules/agent/infra/execution/strategies/<strategy>.py
```

Examples:

```text
standard.py
planner.py
react.py
reflection.py
```

### Runtime resolver

```text
packages/woobe-core/src/modules/agent/infra/execution/strategies/resolver.py
```

This file maps a stable Strategy name to its concrete implementation.

### Product catalog

```text
packages/woobe-core/src/modules/agent/application/execution_strategy_registry.py
```

This file contains product-facing metadata such as display name, description, behavior, recommended use cases, capabilities and limitations.

### Shared Strategy API

```text
packages/woobe-core/src/modules/agent/application/strategy_sdk/
```

A concrete Strategy consumes this API but does not implement its infrastructure.

### Strategy Runtime

```text
packages/woobe-core/src/modules/agent/infra/execution/strategy_runtime/
```

A normal Strategy addition should **not** require changes here. If it does, first determine whether the algorithm actually needs a new reusable primitive or whether runtime plumbing is leaking into the concrete Strategy design.

---

## What the Strategy Runtime already handles

Before implementing a Strategy, assume the following are already runtime responsibilities:

```text
Model/Tool conversation progression
call_index allocation
InstrumentedExecution mutation
Model and Tool instrumentation
durable Tool evidence
checkpoint serialization
State serialization
State restore
legacy checkpoint compatibility
recovery message reconstruction
provider/model preparation
final execution result materialization
```

Do not reimplement these inside a concrete Strategy.

For example, this is correct:

```python
result = await ctx.model.invoke(
    phase=MyPhase.REASONING,
)

batch = await ctx.tools.execute_many(
    result.tool_calls,
)

await ctx.checkpoint()
```

This is intentionally not necessary:

```python
# Do not do this in a concrete Strategy.
messages.append(result.message)
messages.extend(batch.messages)
call_index += 1
cursor = {...}
await recovery.checkpoint(...)
```

The Strategy Runtime owns that work.

---

# Tutorial: creating a new Execution Strategy

The canonical implementation to study is:

```text
packages/woobe-core/src/modules/agent/infra/execution/strategies/standard.py
```

The Standard Strategy demonstrates the complete supported shape: phases, stop reasons, State, Policy, model invocation, Tool execution, checkpointing and completion.

The expected workflow for a new Strategy is:

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

Create a single file directly under `strategies/`.

For example:

```text
packages/woobe-core/src/modules/agent/infra/execution/strategies/planner.py
```

Do not create:

```text
strategies/planner/
├── state.py
├── policy.py
├── phases.py
└── strategy.py
```

The Strategy-specific types belong together because they form one execution algorithm.

Start from the shared contracts:

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

Only import what the algorithm actually needs.

### Standard example

`standard.py` declares one file containing all Standard-specific concepts:

```python
class StandardPhase(ExecutionPhase):
    ...


class StandardStopReason(ExecutionStopReason):
    ...


class StandardExecutionState(ExecutionState):
    ...


class StandardExecutionPolicy(ExecutionPolicy[StandardExecutionState]):
    ...


class StandardExecutionStrategy(
    ExecutionStrategy[StandardExecutionState]
):
    ...
```

That is the preferred shape for future Strategies.

---

## 2. Define State only if the algorithm needs it

`ExecutionState` exists to preserve **algorithm state** across durable checkpoints.

The State must not become a second runtime state container.

### Standard example

The Standard algorithm only needs to remember:

```python
class StandardExecutionState(ExecutionState):
    phase: str | None = None
    tool_round: int = 0
    consecutive_failures: int = 0
    stop_reason: StandardStopReason | None = None
```

Each field directly affects Standard algorithm decisions.

### Good State examples

A Planner may need:

```python
class PlannerExecutionState(ExecutionState):
    current_step: int = 0
    replan_count: int = 0
    plan: list[str] = []
```

A ReAct Strategy may need only:

```python
class ReActExecutionState(ExecutionState):
    iteration: int = 0
```

If an algorithm does not need meaningful durable state, keep State minimal rather than inventing fields.

### State requirements

A concrete State should:

- inherit `ExecutionState`;
- be default-constructible for a fresh execution;
- contain JSON-serializable/Pydantic-compatible data;
- contain only information the algorithm needs to resume decisions;
- rely on the Strategy Runtime for serialization and restore.

A State must not contain:

```text
messages
InstrumentedExecution
call_index
provider clients
Tool executors
recovery objects
checkpoint cursors
runtime services
```

A State must not implement infrastructure methods such as:

```text
create()
restore()
checkpoint_cursor()
checkpoint_messages()
record_model_result()
record_tool_batch()
```

The architecture tests enforce this boundary.

---

## 3. Define Policy only if the algorithm needs it

`ExecutionPolicy` is optional.

Use it when the algorithm has limits or deterministic stop rules that should remain separate from orchestration flow.

### Standard example

```python
@dataclass(frozen=True, slots=True)
class StandardExecutionPolicy(
    ExecutionPolicy[StandardExecutionState]
):
    max_tool_rounds: int = 5
    max_consecutive_failures: int = 2

    def stop_reason(
        self,
        state: StandardExecutionState,
    ) -> StandardStopReason | None:
        if state.consecutive_failures >= self.max_consecutive_failures:
            return StandardStopReason.REPEATED_SEMANTIC_FAILURES

        if state.tool_round >= self.max_tool_rounds:
            return StandardStopReason.CAPABILITY_ROUND_LIMIT

        return None
```

The Policy answers a narrow question:

```text
Given the current algorithm State, should execution stop?
```

A Strategy without meaningful policy rules does not need a Policy class.

Do not create a Policy merely to move arbitrary algorithm code out of `execute()`.

---

## 4. Implement `execute(ctx)`

The main Strategy contract is:

```python
class MyExecutionStrategy(
    ExecutionStrategy[MyExecutionState]
):
    name = "my_strategy"
    state_type = MyExecutionState

    async def execute(
        self,
        ctx: StrategyContext[MyExecutionState],
    ) -> StrategyOutcome:
        ...
```

The stable Strategy-facing primitives are:

```text
ctx.state
ctx.model
ctx.tools
ctx.checkpoint()
```

### Model invocation

```python
result = await ctx.model.invoke(
    phase=MyPhase.REASONING,
)
```

The runtime automatically owns the current conversation and Model call instrumentation.

Do not pass or maintain a separate message history inside the concrete State.

### Tool execution

```python
if result.has_tool_calls:
    batch = await ctx.tools.execute_many(
        result.tool_calls,
    )
```

The runtime automatically records Tool evidence and updates the conversation with the Model/Tool progression.

The Strategy may inspect normalized batch information when that changes algorithm behavior:

```python
if batch.has_failures:
    ctx.state.consecutive_failures += 1
else:
    ctx.state.consecutive_failures = 0
```

### Checkpointing

Checkpoint after a durable algorithm boundary when recovery must resume from the updated State without replaying completed side effects.

Normal usage:

```python
await ctx.checkpoint()
```

An explicit shared boundary may be used when required:

```python
await ctx.checkpoint(
    ExecutionCheckpointBoundary.TOOL,
)
```

The Strategy does not serialize its own State. The Strategy Runtime serializes `ctx.state`, current conversation state, execution evidence and the next call index.

### Completion

Return a Strategy outcome directly:

```python
return Completed(result)
```

Do not mutate `InstrumentedExecution` from the concrete Strategy.

### Standard example

The Standard execution loop is intentionally readable as algorithm code:

```python
result = await ctx.model.invoke(
    phase=state.phase,
)

while result.has_tool_calls and state.tool_round < self.policy.max_tool_rounds:
    tool_batch = await ctx.tools.execute_many(
        result.tool_calls,
    )

    state.tool_round += 1
    state.stop_reason = self.policy.stop_reason(state)

    await ctx.checkpoint()

    if state.stop_reason is not None:
        break

    result = await ctx.model.invoke(
        phase=state.phase,
    )

return Completed(result)
```

The real `standard.py` also handles failure counters, terminal finalization, iterated follow-up phases and the current suspension contract. Use the real implementation as the authoritative example.

---

## 5. Register the Strategy in the resolver

After implementing the file, register the concrete Strategy in:

```text
packages/woobe-core/src/modules/agent/infra/execution/strategies/resolver.py
```

### Standard example

Current resolver:

```python
from modules.agent.infra.execution.strategies.standard import (
    StandardExecutionStrategy,
)


_BUILTIN_EXECUTION_STRATEGY_FACTORIES = {
    StandardExecutionStrategy.name: StandardExecutionStrategy,
}
```

For a new `PlannerExecutionStrategy`:

```python
from modules.agent.infra.execution.strategies.planner import (
    PlannerExecutionStrategy,
)
from modules.agent.infra.execution.strategies.standard import (
    StandardExecutionStrategy,
)


_BUILTIN_EXECUTION_STRATEGY_FACTORIES = {
    StandardExecutionStrategy.name: StandardExecutionStrategy,
    PlannerExecutionStrategy.name: PlannerExecutionStrategy,
}
```

Keep registration explicit.

Do not add auto-discovery, decorators or plugin scanning for built-in Strategies.

The Strategy name must be stable and unversioned:

```text
standard
planner
react
```

Do not introduce:

```text
standard:v1
planner:v2
```

Release snapshots already preserve the selected runtime configuration. A second Strategy-version system is intentionally out of scope.

---

## 6. Register product metadata in the catalog

Runtime implementation and product metadata are intentionally separate.

Add the Strategy descriptor in:

```text
packages/woobe-core/src/modules/agent/application/execution_strategy_registry.py
```

The descriptor is what product/API/UI surfaces use to explain the Strategy.

### Standard example

```python
_STANDARD_DESCRIPTOR = ExecutionStrategyDescriptor(
    name="standard",
    display_name="Standard",
    description=(
        "General-purpose Woobe execution strategy for model and capability orchestration."
    ),
    behavior=(
        "Invokes the configured model, executes bound capabilities when requested, "
        "feeds durable results back into the model, and continues until terminal output "
        "or runtime safety limits are reached."
    ),
    recommended_for=(
        "General-purpose Agents that need predictable production behavior.",
        "Agents that use Tools, Knowledge, structured output, or multi-round capability calls.",
    ),
    capabilities=(
        "Single-pass and multi-round Model execution.",
        "Parallel Tool calls within one capability round.",
        "Durable Tool-boundary recovery without replaying completed Tool side effects.",
        "Structured output validation and JSON repair.",
    ),
    limitations=(
        "Does not add an explicit planning or reflection phase beyond model-directed capability use.",
    ),
    is_default=True,
)
```

A new Strategy should define equivalent metadata and register it in `build_execution_strategy_registry()`:

```python
registry.register(_STANDARD_DESCRIPTOR)
registry.register(_PLANNER_DESCRIPTOR)
```

For normal new Strategies:

```python
is_default=False
```

`standard` is the historical fallback and current default. Do not change the default as part of adding an unrelated Strategy.

Every descriptor must provide non-empty values for:

```text
name
display_name
description
behavior
recommended_for
capabilities
limitations
```

The catalog and runtime resolver must stay in parity.

---

## 7. Add tests

A new Strategy should prove the algorithm itself and prove that it integrates through the generic Strategy Runtime without Strategy-specific runtime changes.

### Behavior tests

Create focused tests for the concrete algorithm under:

```text
tests/unit/agent/
```

Test the decisions that make the Strategy different.

For example, a Planner Strategy should test planning, step progression, stop conditions and final synthesis rather than duplicating generic runtime tests.

### Recovery tests

If the Strategy checkpoints durable progress, test that a simulated restart restores State and does not repeat completed Tool side effects.

The Standard reference is:

```text
tests/unit/agent/test_execution_strategy_standard_recovery.py
```

### SDK/extensibility tests

The generic extension example is:

```text
tests/unit/agent/test_execution_strategy_extensibility.py
```

It demonstrates a non-Standard algorithm implemented through the same SDK without direct capability/runtime plumbing.

### Catalog/resolver parity

The runtime implementation must be represented in the product catalog and vice versa.

Relevant test:

```text
tests/unit/agent/test_execution_strategy_catalog.py
```

### Architecture gates

All flat Strategy files are automatically covered by:

```text
tests/architecture/test_execution_strategy_boundary.py
tests/architecture/execution_strategy/test_strategy_import_quality_gate.py
```

Do not add per-Strategy exceptions unless there is a strong architecture reason.

---

## Standard as the reference implementation

Use `standard.py` as the canonical example when creating another Execution Strategy.

The current Standard file demonstrates the expected order of concepts:

```text
constants
↓
StandardPhase
↓
StandardStopReason
↓
StandardExecutionState
↓
StandardExecutionPolicy
↓
StandardExecutionStrategy
```

Its Strategy declaration is intentionally small:

```python
class StandardExecutionStrategy(
    ExecutionStrategy[StandardExecutionState]
):
    name = "standard"
    state_type = StandardExecutionState
```

Its algorithm interacts with infrastructure only through `StrategyContext`:

```python
state = ctx.state

result = await ctx.model.invoke(...)

tool_batch = await ctx.tools.execute_many(...)

await ctx.checkpoint(...)

return Completed(result)
```

When implementing a new Strategy, first ask:

```text
Can this be expressed with the same primitives?
```

If yes, the change belongs entirely in the new Strategy file plus resolver/catalog/tests.

---

## Rules for State

State is the durable memory of the **algorithm**, not of the entire Run.

Use State for values such as:

```text
tool_round
iteration
current_step
replan_count
stop_reason
selected_branch
algorithm-local observations
```

Do not use State for values already owned by runtime infrastructure:

```text
messages
call_index
InstrumentedExecution
Tool messages
Model messages
provider/model clients
recovery cursor format
checkpoint serialization
stream state
Run lifecycle
```

A useful rule is:

> If removing a field would not change an algorithm decision, the field probably does not belong in concrete Strategy State.

---

## Rules for Policy

Policy is for deterministic algorithm-local limits and stop rules.

Good examples:

```text
max tool rounds
max ReAct iterations
max replans
max consecutive semantic failures
```

Policy should normally inspect State and return a stop reason or no stop reason.

Policy should not own:

```text
Tool execution
Model invocation
checkpoint persistence
Run status
provider calls
arbitrary orchestration
```

If a Strategy has no meaningful policy decision, omit the Policy class.

---

## Rules for phases and stop reasons

The concepts are shared; their concrete values belong to the algorithm.

Use the shared bases:

```python
class MyPhase(ExecutionPhase):
    ...


class MyStopReason(ExecutionStopReason):
    ...
```

The Standard implementation is the reference:

```python
class StandardPhase(ExecutionPhase):
    RESPONSE_GENERATION = "response_generation"
    CAPABILITY_RESPONSE_GENERATION = "capability_response_generation"
    TOOL_FOLLOWUP = "tool_followup"
    FINAL_RESPONSE_GENERATION = "final_response_generation"
```

and:

```python
class StandardStopReason(ExecutionStopReason):
    REPEATED_SEMANTIC_FAILURES = "repeated semantic capability failures"
    CAPABILITY_ROUND_LIMIT = "capability round limit reached"
    PROVIDER_REJECTED_FOLLOWUP = (
        "the capability follow-up request was rejected by the provider"
    )
```

Do not create one global enum containing every future Strategy phase. The shared API owns the concept; each algorithm owns its semantic values.

When an existing observability/recovery contract requires an iterated phase label, use:

```python
strategy_phase_with_iteration(
    MyPhase.STEP,
    iteration,
)
```

instead of hand-building incompatible string conventions.

---

## Architecture rules and forbidden dependencies

Concrete Strategies are deliberately constrained.

They may depend on:

```text
Python standard library
modules.agent.application.strategy_sdk
stable modules.agent.application.interfaces contracts
```

They must not directly depend on:

```text
infra/execution/capabilities
infra/execution/strategy_runtime
persistence/database code
Network implementation
LangChain
provider SDKs
Redis
MongoDB
SQLAlchemy
streaming internals
workers
presentation
composition
```

A concrete Strategy must not access private `StrategyContext` members.

A Strategy must not import another concrete Strategy.

The resolver is the explicit composition point for built-in Strategy implementations.

The architecture tests enforce the flat one-file model and import allowlist.

---

## Validation checklist

Before considering a new Execution Strategy complete, verify all of the following:

- [ ] exactly one new concrete Strategy file was created under `infra/execution/strategies/`;
- [ ] no Strategy-specific package/folder was created;
- [ ] `name` is stable, lowercase and unversioned;
- [ ] `state_type` points to the concrete State;
- [ ] State contains algorithm data only;
- [ ] State is default-constructible and serializable;
- [ ] Policy exists only if there are real algorithm-local rules;
- [ ] Model calls go through `ctx.model`;
- [ ] Tool calls go through `ctx.tools`;
- [ ] durable boundaries use `ctx.checkpoint()`;
- [ ] the Strategy returns `Completed(...)` or another supported `StrategyOutcome`;
- [ ] no runtime/recovery serialization logic exists in the concrete Strategy;
- [ ] the Strategy is registered in `strategies/resolver.py`;
- [ ] product metadata is registered in `execution_strategy_registry.py`;
- [ ] catalog and resolver names match exactly;
- [ ] behavior tests cover the algorithm-specific decisions;
- [ ] recovery tests exist when durable checkpoints are used;
- [ ] architecture gates pass;
- [ ] relevant backend tests pass.

Useful focused validation commands from the repository root include:

```bash
uv run pytest -q \
  tests/unit/agent/test_execution_strategy_catalog.py \
  tests/unit/agent/test_execution_strategy_extensibility.py \
  tests/architecture/test_execution_strategy_boundary.py \
  tests/architecture/execution_strategy/test_strategy_import_quality_gate.py
```

Add the new Strategy's own unit/recovery test files to the focused command.

Do not claim CI, build, typecheck or test success unless those commands/workflows were actually executed.

---

## When the Strategy Runtime should change

Adding a normal Strategy should not require modifying:

```text
infra/execution/strategy_runtime/builder.py
infra/execution/strategy_runtime/context.py
infra/execution/strategy_runtime/model.py
infra/execution/strategy_runtime/tools.py
infra/execution/strategy_runtime/checkpoint.py
infra/execution/strategy_runtime/state.py
infra/execution/strategy_runtime/runtime_state.py
```

If a new algorithm appears to require runtime changes, first classify the requirement.

### Strategy-specific behavior

If the behavior is unique to the algorithm, keep it in the concrete Strategy file.

Examples:

```text
planning order
reflection loop
replan policy
step selection
algorithm-specific termination
```

### Shared execution primitive

If multiple Strategies need the same runtime capability and it cannot be expressed through the current SDK, then a small shared primitive may belong in `strategy_sdk` + `strategy_runtime`.

Examples could include a future generic structured-model invocation or a fully supported suspension/resume primitive.

Do not modify Strategy Runtime merely to make one concrete Strategy more convenient if the behavior is actually algorithm-specific.

---

## Current limitation: suspension

The Strategy SDK can currently represent:

```python
Suspended(...)
```

but the outer Agent Run lifecycle does not yet enable the complete `RUNNING -> WAITING -> RESUME` behavior.

Therefore, suspension is currently a contract boundary for future durable async execution, not a generally available production lifecycle capability.

Do not design a new built-in Strategy that requires suspension to function correctly until the outer WAITING lifecycle is implemented.

---

## Quick reference

To add a new built-in Execution Strategy:

```text
1. Create:
   infra/execution/strategies/<name>.py

2. In that file:
   - Phase, if needed
   - StopReason, if needed
   - State, if needed
   - Policy, if needed
   - <Name>ExecutionStrategy.execute(ctx)

3. Register runtime implementation:
   infra/execution/strategies/resolver.py

4. Register product metadata:
   application/execution_strategy_registry.py

5. Add tests:
   tests/unit/agent/

6. Verify architecture gates:
   tests/architecture/test_execution_strategy_boundary.py
   tests/architecture/execution_strategy/test_strategy_import_quality_gate.py
```

The target developer experience is deliberate:

```text
create one file
→ write the algorithm
→ register it
→ describe it
→ test it
```

If creating a new Strategy requires understanding checkpoint cursor formats, message reconstruction, call indexes, `InstrumentedExecution`, provider adapters or persistence internals, the abstraction boundary has regressed and should be corrected instead of copied into the new Strategy.
