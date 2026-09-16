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

A Strategy file may contain its own phase enum, stop-reason enum, state, policy and algorithm. Those types stay together because they are one cohesive algorithm. Shared concepts do not get reimplemented per Strategy: they belong to `application/strategy_sdk` and are implemented by each Strategy through stable contracts such as `ExecutionState` and `ExecutionPolicy`.

Concrete Strategies receive only `StrategyContext` and may use the shared primitives exposed by it: Model operations, Tool operations, durable checkpoints, completion and suspension. They do not prepare providers, allocate call indexes, persist recovery data, finalize Agent Runs, write databases, stream SSE, or import runtime lifecycle infrastructure.

Checkpoint boundaries are shared through `ExecutionCheckpointBoundary`. Strategy phases remain local when they describe algorithm-specific behavior. Iterated phase names use the shared phase helper instead of hand-built string conventions.

To add a built-in Strategy:

1. Create one file in this directory, for example `planner.py`.
2. Implement a Strategy-specific `ExecutionState` in that file.
3. Implement a Strategy-specific `ExecutionPolicy` when the algorithm needs limits or stop rules.
4. Define local phase and stop-reason enums only for semantics unique to the algorithm.
5. Implement `ExecutionStrategy.execute(ctx)` using only the Strategy SDK.
6. Register the Strategy factory in `resolver.py` and its product descriptor in `execution_strategy_registry.py`.
7. Add behavior and recovery tests. Architecture gates automatically cover every flat Strategy file.

Do not create a package per Strategy, a second strategy-version system, plugin discovery or direct provider/runtime dependencies inside Strategy files.
