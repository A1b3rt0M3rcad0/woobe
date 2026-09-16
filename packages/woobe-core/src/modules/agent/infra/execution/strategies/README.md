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

To add a built-in Strategy:

1. Create one file in this directory, for example `planner.py`.
2. Define a small Strategy-specific `ExecutionState` only when the algorithm needs durable state.
3. Define an `ExecutionPolicy` only when the algorithm needs limits or stop rules.
4. Define local phase and stop-reason enums only for semantics unique to the algorithm.
5. Implement `ExecutionStrategy.execute(ctx)` using only the Strategy SDK.
6. Register the Strategy factory in `resolver.py` and its product descriptor in `execution_strategy_registry.py`.
7. Add behavior and recovery tests. Architecture gates automatically cover every flat Strategy file.

Do not create a package per Strategy, a per-Strategy codec/factory, a second strategy-version system, plugin discovery or direct provider/runtime dependencies inside Strategy files.
