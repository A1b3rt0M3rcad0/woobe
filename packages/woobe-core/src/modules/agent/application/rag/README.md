# Agent RAG subsystem

The RAG subsystem separates behavior from infrastructure.

- **Strategy** owns the retrieval algorithm and decides how capabilities are composed.
- **Capability** exposes a reusable operation required by one or more strategies.
- **Adapter** connects capabilities and strategy execution to Woobe runtime infrastructure.

The first strategy is `classic`, which preserves the existing vector-snapshot retrieval behavior. Strategy names are intentionally simple (`classic`, `agentic`, `hyde`, ...); this subsystem does not introduce an independent `:v1` version axis.

## Extension rules

1. A strategy must depend only on application contracts/capabilities, never directly on `infra`.
2. Add a capability only when a concrete strategy actually needs it.
3. Storage, provider credentials, SQL transactions and vendor SDKs stay behind infrastructure adapters.
4. Missing `runtime_config.rag.strategy` resolves to `classic` for backward compatibility.
5. An explicit unknown strategy fails deterministically; there is no silent fallback to `classic`.
6. Strategies must not keep mutable per-Run state on shared instances. Invocation state belongs to the request/capabilities/local call stack.
7. Acceptance remains responsible for freezing the Knowledge/VectorSnapshot binding. A strategy may use that binding; it may not replace it with a newer mutable one.
