# Agent Execution Strategies

This package is the extension point for concrete Agent execution algorithms.

The stable Runtime boundary is:

```text
modules/agent/application/interfaces/execution_strategy.py
```

An Execution Strategy controls **how an Agent conducts model/capability execution**. It may decide model invocation order, capability-loop behavior, continuation, termination, planning or reflection. It does not own Agent Run lifecycle, persistence, Release resolution, Session continuity, Tool Policy, Human Approval, Context Engineering, streaming, cancellation, Project isolation or Network orchestration.

## Strategy identity

Strategy identity is intentionally simple and unversioned:

```text
standard
react
plan_execute
```

Do not introduce identities such as `standard:v1` or a second strategy-version system. Agent and Release snapshots already freeze `runtime_config.execution_strategy`.

Historical snapshots without the field are permanently interpreted as `standard`.

## Current strategy

```text
standard -> StandardExecutionStrategy
```

`StandardExecutionStrategy` delegates to the existing `run_instrumented_execution()` behavior. This preserves the current engine while placing it behind a replaceable contract.

## Adding a future built-in strategy

1. Implement `ExecutionStrategy` in this directory.
2. Give it a stable semantic name.
3. Register it explicitly in `resolver.py`.
4. Add the name to backend configuration validation.
5. Add focused behavior, recovery and architecture tests.

Do not add plugin discovery, external adapters or Network-specific strategy selection unless those requirements are independently justified.
