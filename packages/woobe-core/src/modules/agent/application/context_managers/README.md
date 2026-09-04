# Context Managers

This package is the explicit extension point for concrete Agent Context Manager strategies.

The Runtime boundary is **not** implemented here. The boundary is:

```text
modules/agent/application/interfaces/context_assembler.py
```

Runtime/execution code depends only on `ContextAssembler`. Concrete strategies live in this directory and are selected through `context_assembler_registry.py`.

## Add a new built-in Context Manager

1. Create one strategy module here, for example `adaptive.py`.
2. Implement the structural `ContextAssembler` contract:

   ```python
   class AdaptiveContextAssembler:
       def assemble(
           self,
           request: ContextAssemblyRequest,
       ) -> ContextAssemblyOutput:
           ...
   ```

3. Give the strategy a stable versioned identity such as `adaptive:v1`.
4. Add complete backend-owned `ContextAssemblerDescriptor` metadata in `context_assembler_registry.py`.
5. Register the concrete strategy in `_register_builtin_context_manager_strategies(...)` in `context_assembler_registry.py`.
6. Add focused strategy/registry tests. The API and frontend catalog are populated from the Registry; do not hardcode the strategy in the frontend.

## Versioning rules

- Never change the meaning of an identity already referenced by Agent/Release snapshots. Publish a new version instead (`adaptive:v1` -> `adaptive:v2`).
- `default` is reserved for the System Default alias. Concrete strategies must use their own identity.
- `WOOBE_DEFAULT_CONTEXT_MANAGER` points to a concrete registered strategy such as `stdcm:v1`, never `default:v1`.
- Existing snapshots keep both their selection identity and frozen concrete strategy identity for replay and rollback.

## Runtime rules

- Do not import a concrete Context Manager from `infra/execution`.
- Do not add strategy-specific branches to Agent Runtime invocation paths.
- Keep per-invocation mutable state inside `ContextAssemblyRequest`/local call scope. Runtime may share one manager instance across concurrent Runs.
- Context Managers decide how context is assembled. They do not own model execution, Tool execution, Run lifecycle, Knowledge storage, or Network orchestration.

## Current built-in strategy

```text
stdcm:v1 -> StandardContextAssembler
```

Implementation:

```text
modules/agent/application/context_managers/standard.py
```

The Standard strategy currently delegates to the existing deterministic `context_assembly.py` algorithm. Future strategies may use different internal algorithms while preserving the same `ContextAssembler` boundary.
