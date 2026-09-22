# Context Manager Documentation

Context Managers are Woobe's programmable context-selection algorithms. They use the same architectural principle as Execution Strategies: concrete algorithm code sits above a narrow SDK, while a shared runtime owns infrastructure, invariants and evidence.

Use [`../standard.py`](../standard.py) as the canonical concrete implementation while reading these documents.

## Index

1. [Architecture and mental model](./architecture.md)
2. [Creating a Context Manager](./creating-a-manager.md)
3. [Context Policy](./policy.md)
4. [SDK primitives](./primitives.md)
5. [Source and transformation model](./source-model.md)
6. [State and lifecycle](./state-and-lifecycle.md)
7. [Context evidence and observability](./evidence.md)
8. [Summary and compaction](./summary-and-compaction.md)
9. [Resolver and product catalog](./resolver-and-catalog.md)
10. [Testing and validation](./testing.md)
11. [Architecture rules](./architecture-rules.md)
12. [Current limitations](./limitations.md)

## Recommended reading order

~~~text
architecture.md
      ↓
policy.md
      ↓
primitives.md
      ↓
source-model.md
      ↓
state-and-lifecycle.md / evidence.md
      ↓
creating-a-manager.md
      ↓
summary-and-compaction.md
      ↓
resolver-and-catalog.md
      ↓
testing.md
~~~

If you only need the implementation checklist, go directly to [Creating a Context Manager](./creating-a-manager.md).
