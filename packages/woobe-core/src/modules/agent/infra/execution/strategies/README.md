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

## Shared execution capabilities

Strategies must compose the execution operations exposed under:

```text
modules/agent/infra/execution/capabilities/
```

The capability layer currently separates:

- execution preparation and resolved model/tool binding;
- durable/instrumented model invocation;
- governed durable Tool execution;
- strategy-local execution state;
- structured result finalization.

A Strategy may decide when and how often these capabilities are used, but it must not bypass the runtime-governed invocation paths. In particular, concrete Strategies must not call provider adapters, Tool integrations, persistence or Agent Run lifecycle services directly.

`run_instrumented_execution()` remains only as a compatibility entrypoint for existing callers. It is not the extension API for new Strategies.

## Current strategy

```text
standard -> StandardExecutionStrategy
```

`StandardExecutionStrategy` now composes execution preparation, the current capability-aware Standard loop and result finalization directly. It no longer depends on `run_instrumented_execution()` as its algorithm boundary.

The current `run_tool_loop()` still preserves the existing Standard loop semantics, including durable Tool barriers, recovery checkpoints, circuit breaking and terminal recovery. Further decomposition of that loop must preserve those guarantees before the Standard Strategy owns lower-level loop orchestration directly.

## Adding a future built-in strategy

1. Implement `ExecutionStrategy` in this directory.
2. Compose shared execution capabilities instead of the legacy runner.
3. Give the Strategy a stable semantic name.
4. Register it explicitly in `resolver.py`.
5. Add the name to backend configuration validation.
6. Add focused behavior, recovery, observability and architecture tests.

Do not add plugin discovery, external adapters or Network-specific strategy selection unless those requirements are independently justified.
