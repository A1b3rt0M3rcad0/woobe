# Knowledge Runtime Strategies

This package is the explicit extension point for concrete Agent Knowledge retrieval strategies.

The Runtime boundary is defined in:

```text
modules/agent/application/interfaces/knowledge_strategy.py
```

Runtime code must depend on `KnowledgeRuntimeStrategy`, not on a concrete retrieval implementation.

## Current built-in strategy

```text
std-rag:v1 -> StandardVectorRAGStrategy
```

`std-rag:v1` preserves the original Woobe immutable Vector Snapshot + similarity retrieval behavior. Historical Agent/Release snapshots without explicit strategy identity resolve to this strategy.

## Add a strategy

1. Create one strategy module in this directory.
2. Implement `KnowledgeRuntimeStrategy.prepare(...)` and `retrieve(...)`.
3. Assign a stable versioned identity such as `hybrid-rag:v1`.
4. Register it in `knowledge_strategy_registry.py` with backend-owned metadata.
5. Add focused strategy and registry tests.

Never change the behavior represented by a published identity. Publish a new version instead.

A strategy owns how Knowledge is prepared and retrieved. It does not own Context Engineering, model execution, Tool execution, Run lifecycle, Knowledge storage lifecycle, or Network orchestration.
