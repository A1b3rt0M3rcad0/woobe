# Execution Strategy Documentation

This directory contains the implementation guide for Agent Execution Strategies.

Use [`../standard.py`](../standard.py) as the canonical reference implementation while reading these documents.

## Index

1. [Architecture and mental model](./architecture.md)
   - what a Strategy owns;
   - what the Strategy Runtime owns;
   - when runtime changes are justified.

2. [Creating a new Execution Strategy](./creating-a-strategy.md)
   - the complete implementation workflow;
   - one file per Strategy;
   - `execute(ctx)`;
   - registration and validation.

3. [Execution State](./state.md)
   - when State is needed;
   - what belongs in State;
   - what must stay in the Runtime;
   - `StandardExecutionState` as reference.

4. [Execution Policy](./policy.md)
   - when Policy is useful;
   - stop rules and algorithm limits;
   - `StandardExecutionPolicy` as reference.

5. [Phases and stop reasons](./phases-and-stop-reasons.md)
   - Strategy-specific phases;
   - Strategy-specific stop reasons;
   - iterated phases.

6. [Resolver and product catalog](./resolver-and-catalog.md)
   - runtime registration in `resolver.py`;
   - product metadata in `execution_strategy_registry.py`;
   - keeping both in parity.

7. [Testing and validation](./testing.md)
   - behavior tests;
   - recovery tests;
   - catalog/resolver parity;
   - architecture gates;
   - Definition of Done.

8. [Architecture rules](./architecture-rules.md)
   - allowed dependencies;
   - forbidden dependencies;
   - one-file convention;
   - rules enforced by the Quality Gate.

9. [Suspension and current limitations](./suspension.md)
   - current `Suspended` contract;
   - why `WAITING -> RESUME` is not generally available yet.

## Recommended reading order

If you are implementing a Strategy for the first time:

```text
architecture.md
      ↓
creating-a-strategy.md
      ↓
state.md / policy.md
      ↓
phases-and-stop-reasons.md
      ↓
resolver-and-catalog.md
      ↓
testing.md
```

If you already understand the architecture and only need the implementation checklist, go directly to [Creating a new Execution Strategy](./creating-a-strategy.md).
