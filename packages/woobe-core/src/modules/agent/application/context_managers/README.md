# Context Managers

Context Managers define **how Woobe assembles the effective context for each Model Invocation**.

The target programming model mirrors Execution Strategies:

```text
Concrete Context Manager
        │
        ▼
ContextManagerContext
        │
        ▼
Context Manager Runtime
        │
        ▼
ContextAssembler
        │
        ▼
Model Invocation
```

Concrete Managers own the context-selection algorithm. Shared runtime code owns classification, budgets, materialization, Context Snapshots, provenance, integrity rules, and provider-facing assembly.

## Stable identities

Context Managers use stable, unversioned product identities, following the same model as Execution Strategies.

Examples:

```text
standard
adaptive
long-horizon
```

Do not publish product identities such as:

```text
stdcm:v1
stdcm:v2
adaptive:v3
```

The implementation of a Manager may evolve while its semantic identity remains stable. Compatibility for historical persisted identities belongs to migration/runtime compatibility code rather than the selectable Manager catalog.

## Standard

`standard` is the canonical general-purpose Context Manager.

Skills support is part of Standard behavior. The previous split between `stdcm:v1` and `stdcm:v2` is being consolidated; there is no separate public "Standard v2" Manager.

## Target developer workflow

A normal new Context Manager should require approximately:

```text
1. create one Manager file
2. implement assemble(ctx)
3. select/cap/order context sources
4. apply budget behavior
5. complete the context
6. register in the resolver
7. register product metadata
8. test
```

Adding one normal Manager should not require modifying Context Manager Runtime internals.

## Runtime rules

- Context Managers decide the assembly algorithm.
- Managers do not own model execution, Tool execution, Run lifecycle, persistence, Knowledge storage, or Network orchestration.
- Provider integrity, mandatory context invariants, budget enforcement, snapshots, hashes, and provenance belong to the shared Context Manager Runtime.
- Runtime/execution code depends on stable Context Manager/ContextAssembler contracts, not concrete Manager implementations.
