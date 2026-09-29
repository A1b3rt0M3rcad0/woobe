# Agent Knowledge / RAG subsystem

Knowledge and RAG are separate programmable layers.

```text
ExecutionStrategy
      │
      │ decides when retrieval is needed
      ▼
StrategyKnowledge
      │
      ▼
KnowledgeStrategy
      │
      │ owns conversation-to-query policy
      │ and Knowledge-level retrieval behavior
      ▼
KnowledgeCapabilities
      │
      ▼
RAG runtime (for the built-in "rag" Knowledge Strategy)
      │
      ▼
RAGStrategy
      │
      │ owns the concrete RAG algorithm
      ▼
embedding / vector-search capabilities
```

The built-in Knowledge Strategy is `rag`. It receives the read-only conversation,
constructs the final retrieval query and delegates that query to the frozen RAG
runtime binding.

The RAG subsystem remains independently programmable. Its first Strategy is
`classic`, which preserves the vector-snapshot retrieval behavior. Future RAG
algorithms such as `agentic`, `hyde` or hybrid retrieval can use the same
Knowledge Strategy while changing only the nested retrieval algorithm.

This distinction is intentional:

- **Execution Strategy** owns *when* Knowledge is requested and whether its result is included in Context.
- **Knowledge Strategy** owns *how the execution conversation becomes a Knowledge request* and how Knowledge capabilities are composed.
- **Knowledge Capability** owns runtime-governed mechanisms and contains no query policy.
- **RAG Strategy** owns a RAG retrieval algorithm after it receives an already-final query.
- **Context Manager** owns how the returned Knowledge contribution is materialized into an invocation.
- **Runtime** owns frozen bindings, credentials, persistence, recovery, instrumentation and authorization.

## Configuration

Knowledge Strategy selection is independent from RAG Strategy selection:

```json
{
  "knowledge_strategy": "rag",
  "rag": {
    "strategy": "classic",
    "query_mode": "conversation_context",
    "history_turns": 3
  }
}
```

Missing `knowledge_strategy` permanently resolves to `rag` for historical
snapshots. Mutable Agent configuration canonicalizes the selection explicitly.
Historical Release snapshots are not rewritten merely to add the field.

The current `rag` Knowledge Strategy continues to read `query_mode` and
`history_turns` from `runtime_config.rag` for compatibility. That location is
configuration for the built-in RAG-backed Knowledge Strategy; it is not an
Execution Strategy concern.

## Adding a Knowledge Strategy

A new Knowledge implementation should satisfy
`application.interfaces.knowledge.KnowledgeStrategy`, use only the mechanisms
exposed by `KnowledgeCapabilities`, and be registered in
`application.knowledge_strategy_registry`.

A normal Knowledge Strategy must not require changes to
`StandardExecutionStrategy`, `StrategyContext` or the Context Manager. If a new
Knowledge algorithm needs a reusable mechanism that the current capability surface
cannot express, extend `KnowledgeCapabilities` and bind that mechanism in the
runtime rather than leaking backend details into Execution.

Examples of future Knowledge Strategies include a PageIndex-backed strategy, WKS
strategy, graph Knowledge strategy or a hybrid strategy. Those strategies may use a
different backend binding while preserving the same Execution-facing
`ctx.knowledge.retrieve(conversation=...)` contract.

## RAG extension rules

1. A RAG Strategy depends only on application contracts/capabilities, never directly on `infra`.
2. Add a RAG capability only when a concrete RAG Strategy actually needs it.
3. Storage, provider credentials, SQL transactions and vendor SDKs stay behind infrastructure adapters.
4. Missing `runtime_config.rag.strategy` resolves to `classic` for backward compatibility.
5. An explicit unknown RAG Strategy fails deterministically; there is no silent fallback to `classic`.
6. Strategies must not keep mutable per-Run state on shared instances. Invocation state belongs to requests, capabilities or the local call stack.
7. Acceptance remains responsible for freezing the Knowledge/VectorSnapshot binding. A RAG Strategy may use that binding; it may not replace it with newer mutable state.
