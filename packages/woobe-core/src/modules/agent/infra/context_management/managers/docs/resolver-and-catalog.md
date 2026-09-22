# Resolver and product catalog

A built-in Context Manager must be registered in two places with different responsibilities.

## Runtime resolver

File:

~~~text
packages/woobe-core/src/modules/agent/infra/context_management/managers/resolver.py
~~~

The resolver maps a stable Manager name to the concrete algorithm implementation and wraps it in the shared `ContextManagerRunner`.

Current Standard registration:

~~~python
_BUILTIN_CONTEXT_MANAGER_FACTORIES = {
    StandardContextManager.name: StandardContextManager,
}
~~~

Adding another built-in Manager:

~~~python
_BUILTIN_CONTEXT_MANAGER_FACTORIES = {
    StandardContextManager.name: StandardContextManager,
    KnowledgeFirstContextManager.name: KnowledgeFirstContextManager,
}
~~~

Keep registration explicit. Do not add filesystem scanning, decorators or auto-discovery for built-ins.

The resolver owns **runtime implementation selection**, not product metadata.

## Runtime dispatcher

`build_runtime_context_assembler(...)` creates a snapshot-aware `ResolvedContextAssembler`.

Its job is:

~~~text
read canonical manager name from invocation context
        ↓
fall back to configured system default when absent
        ↓
resolve concrete built-in Manager
        ↓
run through ContextManagerRunner
~~~

The execution path still depends only on the outer `ContextAssembler` contract.

## Product catalog

File:

~~~text
packages/woobe-core/src/modules/agent/application/context_manager_registry.py
~~~

The catalog describes selectable Managers to API/frontend/product surfaces. It must not import concrete infrastructure Manager classes.

A descriptor owns fields such as:

~~~text
name
display_name
description
behavior
recommended_for
capabilities
limitations
configuration
supports_skills
is_default
~~~

The descriptor should describe behavior that really exists. Do not advertise semantic summary, artifact materialization modes or other unsupported Runtime capabilities.

## Resolver versus catalog

~~~text
resolver.py
= which implementation executes

context_manager_registry.py
= how Woobe exposes/describes the Manager as a product capability
~~~

Keeping these separate prevents Application/product code from depending on infrastructure implementations.

## Naming rules

Manager names are stable, lowercase and unversioned:

~~~text
standard
adaptive
knowledge-first
long-horizon
~~~

Do not introduce:

~~~text
standard:v1
standard:v2
adaptive:v3
~~~

Release snapshots already freeze the selected manager name and Context Policy. A second Manager-version namespace would duplicate versioning concerns.

## Historical compatibility

Old persisted selections are read-compatible and normalize to `standard`:

~~~text
stdcm:v1
stdcm:v2
default:v1
stdcm
default
~~~

These are compatibility inputs only. They must not reappear as selectable catalog identities.

## Parity requirement

Every selectable catalog Manager must resolve at runtime, and every built-in runtime Manager intended for product selection must have catalog metadata.

`tests/unit/agent/test_context_manager_programming.py` checks resolver/catalog parity.

## System default

`standard` remains the canonical default unless changing the default is an explicit product decision.

Changing the system default must not reinterpret historical frozen snapshots.
