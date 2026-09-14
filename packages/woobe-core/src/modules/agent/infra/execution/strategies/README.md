# Agent Execution Strategies

This package is the extension point for concrete Agent execution algorithms.

The stable Runtime boundary is:

```text
modules/agent/application/interfaces/execution_strategy.py
```

An Execution Strategy controls **how an Agent conducts model/capability execution**. It may decide model invocation order, capability-loop behavior, continuation, termination, planning or reflection. It does not own Agent Run lifecycle, persistence, Release resolution, Session continuity, Tool Policy, Human Approval, Context Engineering infrastructure, streaming transport, cancellation infrastructure, Project isolation or Network orchestration.

## Strategy identity

Strategy identity is intentionally simple and unversioned:

```text
standard
react
plan_execute
```

Do not introduce identities such as `standard:v1` or a second strategy-version system. Agent and Release snapshots already freeze `runtime_config.execution_strategy`.

Historical snapshots without the field are permanently interpreted as `standard`.

## Shared execution capabilities

Strategies compose the execution operations exposed under:

```text
modules/agent/infra/execution/capabilities/
```

The capability layer separates:

- execution preparation and resolved model/Tool/Skill bindings;
- durable/instrumented model invocation;
- governed durable Tool execution;
- message progression helpers;
- strategy-local execution state;
- strategy-neutral durable recovery checkpoints with an opaque Strategy cursor;
- structured result finalization.

A Strategy decides when, how often and in what order these capabilities are used, but it must not bypass the runtime-governed invocation paths. Concrete Strategies must not call provider adapters, Tool integrations, persistence or Agent Run lifecycle services directly.

The recovery contract deliberately does not understand Standard-specific loop semantics. Each Strategy owns an opaque `strategy_cursor` and the recovery capability persists/restores it together with durable capability messages and execution evidence. Legacy Standard checkpoints remain readable for backwards compatibility.

## Current strategy

```text
standard -> StandardExecutionStrategy
```

`StandardExecutionStrategy` owns the complete Standard orchestration: initial model invocation, Tool batches, follow-up rounds, circuit breaking, durable continuation checkpoints and terminal recovery. It composes shared capabilities and no longer depends on `run_instrumented_execution()` or `run_tool_loop()` as its algorithm boundary.

`run_instrumented_execution()` and `run_tool_loop()` remain compatibility facades for existing focused callers/tests. Both delegate into the same Standard Strategy implementation rather than maintaining a second algorithm.

## Adding a future built-in strategy

1. Implement `ExecutionStrategy` in this directory.
2. Resolve execution inputs through `prepare_execution()`.
3. Build shared capabilities with a stable Strategy name.
4. Keep algorithm-local state inside the Strategy and/or `StrategyExecutionState`.
5. Use `capabilities.model` for every model invocation.
6. Use `capabilities.tools` for every Tool execution.
7. Persist recovery boundaries through `capabilities.recovery` with an opaque Strategy cursor when the algorithm has durable continuation points.
8. Finalize structured output through the shared result finalization capability.
9. Register the Strategy explicitly in `resolver.py` and backend configuration validation.
10. Add behavior, release/recovery, observability and architecture tests.

Do not add plugin discovery, external adapters or Network-specific strategy selection unless those requirements are independently justified.
