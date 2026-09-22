# Context Manager Documentation

Context Managers are Woobe's programmable, asynchronous context-management algorithms. Concrete Managers own algorithm decisions; Context Manager Runtime owns provider I/O, materialization, summary execution, checkpoint durability, recovery mechanics and evidence.

Use `standard.py` for the minimal deterministic reference and `adaptive.py` for stateful async summary/checkpoint patterns.

## Index

1. [Architecture and mental model](./architecture.md)
2. [Standard and Adaptive](./standard-and-adaptive.md)
3. [Creating a Context Manager](./creating-a-manager.md)
4. [Context Policy](./policy.md)
5. [SDK primitives](./primitives.md)
6. [Source and transformation model](./source-model.md)
7. [State and lifecycle](./state-and-lifecycle.md)
8. [Context evidence and observability](./evidence.md)
9. [Summary and compaction](./summary-and-compaction.md)
10. [Resolver and product catalog](./resolver-and-catalog.md)
11. [Testing and validation](./testing.md)
12. [Architecture rules](./architecture-rules.md)
13. [Current limitations](./limitations.md)

## Recommended reading order

~~~text
architecture.md
      ↓
standard-and-adaptive.md
      ↓
policy.md / primitives.md
      ↓
source-model.md
      ↓
state-and-lifecycle.md
      ↓
summary-and-compaction.md / evidence.md
      ↓
creating-a-manager.md
      ↓
resolver-and-catalog.md
      ↓
testing.md / architecture-rules.md
~~~

## Core rule

> Managers decide what context behavior is required. Runtime primitives perform mechanics and side effects.

That rule is the Context equivalent of the Execution Strategy/Strategy Runtime separation.
