# Resolver and product catalog

Built-in Context Managers have separate runtime implementation and product metadata registration.

## Runtime resolver

File:

~~~text
infra/context_management/managers/resolver.py
~~~

Current built-ins:

~~~python
_BUILTIN_CONTEXT_MANAGER_FACTORIES = {
    StandardContextManager.name: StandardContextManager,
    AdaptiveContextManager.name: AdaptiveContextManager,
}
~~~

The resolver creates shared `ContextManagerRunner` adapters and keeps registration explicit.

Do not add decorators, filesystem scanning or auto-discovery for built-ins.

## Runtime dispatcher

`build_runtime_context_assembler()` returns a snapshot-aware `ResolvedContextAssembler` that reads the canonical Manager name from execution context and awaits the resolved async assembler.

The Agent execution path still depends only on the outer `ContextAssembler` contract.

## Product catalog

File:

~~~text
application/context_manager_registry.py
~~~

The catalog owns product-facing metadata and must not import concrete Manager implementations.

Current product identities:

~~~text
standard
adaptive
~~~

Standard is the default. Adaptive is selectable and advertises capacity-aware source management, optional semantic summary and durable run-local Context state.

## Identity parity

Every selectable catalog Manager must resolve at runtime, and every selectable built-in runtime Manager must have a descriptor.

Tests enforce this set equality.

## Stable unversioned names

Use:

~~~text
standard
adaptive
knowledge-first
long-horizon
~~~

Do not create `adaptive:v2` or `standard:v3`. Release snapshots already freeze Manager selection and Context Policy.

## Historical compatibility

These old values remain read-only aliases to `standard`:

~~~text
stdcm:v1
stdcm:v2
default:v1
stdcm
default
~~~

They must not reappear in the selectable catalog.

## Configured system default

The registry can mark either registered Manager as the process-configured default for new snapshots, but historical snapshots with missing selection permanently resolve to the historical `standard` fallback unless explicitly canonicalized for a new mutable snapshot.
