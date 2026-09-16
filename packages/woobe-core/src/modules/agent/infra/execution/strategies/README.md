# Agent Execution Strategies

This package is the extension point for concrete Agent execution algorithms.

The stable algorithm boundary is the internal Strategy SDK:

```text
modules/agent/application/strategy_sdk/
modules/agent/application/interfaces/execution_strategy.py
```

A concrete Strategy controls **how an Agent conducts model/capability execution**. It may decide invocation order, Tool loops, planning, reflection, replanning and termination. It does not own Agent Run lifecycle, persistence, Release resolution, Session continuity, Tool Policy, Human Approval, Context Engineering infrastructure, streaming transport, cancellation infrastructure, Project isolation or Network orchestration.

## Dependency law

The dependency direction is intentional and enforced by architecture tests:

```text
concrete Strategy
      ↓
application/strategy_sdk
      ↓
infra/execution/strategy_runtime
      ↓
infra/execution/capabilities
      ↓
durable runtime infrastructure
```

Concrete Strategies must not import runtime implementations, capabilities, databases, streaming, provider SDKs, workers, Network orchestration or another concrete Strategy. `strategies/resolver.py` is the only composition point allowed to know concrete Strategy definitions.

The Strategy SDK must remain infrastructure-free. The Strategy Runtime is the authorized bridge from the SDK to runtime capabilities.

## Strategy identity

Strategy identity is intentionally simple and unversioned:

```text
standard
react
plan_execute
```

Do not introduce identities such as `standard:v1` or a second strategy-version system. Agent and Release snapshots already freeze `runtime_config.execution_strategy`. Historical snapshots without the field are permanently interpreted as `standard`.

## Backend registry and product contract

Selectable Strategy metadata is backend-owned and lives in:

```text
modules/agent/application/execution_strategy_registry.py
```

The registry exposes presentation metadata consumed by API/UI surfaces. Concrete runtime implementations remain behind `ExecutionStrategyResolver`, and architecture tests keep registry identities aligned with executable implementations.

## Internal Strategy API

Concrete algorithms receive only `StrategyContext`:

```text
ctx.state
ctx.model
ctx.tools
ctx.checkpoint()
ctx.complete()
ctx.suspend()
```

`ctx.model` hides model call indexing, durable instrumentation, Context Engineering and provider invocation. `ctx.tools` hides governed Tool execution and Tool evidence. `ctx.checkpoint()` persists the opaque Strategy cursor through the shared recovery capability. `ctx.complete()` produces a Strategy outcome without finalizing the outer Agent Run lifecycle.

The suspension outcome is part of the SDK contract so async Tools/Human Approval can be added without redesigning concrete algorithms. The outer Agent Run WAITING lifecycle is intentionally not enabled by this refactor yet.

## Standard Strategy

The built-in Standard Strategy lives under:

```text
strategies/standard/
```

- `strategy.py` contains the algorithm only;
- `state.py` contains algorithm-local state plus state codec/factory;
- `policy.py` owns limits and stop decisions;
- `phases.py` centralizes phase/boundary identities;
- `definition.py` composes the Strategy factory, state factory and codec;
- `compat.py` keeps legacy focused entrypoints delegating to the same algorithm.

The Standard algorithm must remain readable without understanding persistence, streaming, recovery storage or provider adapters.

## Adding a future built-in Strategy

A new Strategy should normally require only its own algorithm/state/policy/phases/codec plus registration in the resolver and product registry. If adding a Strategy requires editing Agent Run lifecycle, persistence, streaming or recovery infrastructure, either the SDK boundary is incomplete or the requirement is a genuinely reusable runtime capability that should be added below the SDK.

Do not add plugin discovery, external adapters or Network-specific strategy selection unless those requirements are independently justified.
