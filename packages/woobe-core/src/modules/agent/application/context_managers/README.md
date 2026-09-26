# Context Managers

This package is the explicit extension point for concrete Agent Context Manager strategies.

The Runtime boundary is **not** implemented here. The boundary is:

```text
modules/agent/application/interfaces/context_assembler.py
```

Runtime/execution code depends only on the stable `ContextAssembler` compatibility contract. Despite the historical name, this is now the full Context Manager interface: `inspect`, `compact` and `assemble`. Concrete strategies live in this directory and are selected through `context_assembler_registry.py`.

## Add a new built-in Context Manager

1. Create one strategy module here, for example `adaptive.py`.
2. Implement the structural `ContextAssembler` contract:

   ```python
   class AdaptiveContextAssembler:
       def inspect(
           self,
           request: ContextInspectionRequest,
       ) -> ContextInspectionOutput:
           ...

       async def compact(
           self,
           request: ContextCompactionRequest,
           capabilities: ContextManagerCapabilities,
       ) -> ContextCompactionOutput:
           ...

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

The Standard strategy owns pressure inspection and session compaction, including model-assisted summarize-and-replace when pressure is high, then delegates final deterministic materialization to `context_assembly.py`. Other managers may implement completely different management algorithms while preserving the same interface.

## Standard v2: Skills

`stdcm:v2` is composed by the registry as `StandardSkillsContextAssembler` with a standard assembler dependency. It materializes Run-local Skill catalog, instruction and resource contributions, protects complete procedures from compaction and records package/version provenance. Its activation state belongs to the Run, not the shared manager instance. The system default remains `stdcm:v1`; published v1 identities retain their behavior.

See [Agent Skills](../../../../../../../docs/skills/README.md) for package, API, budget and rollout contracts. Manager catalog metadata declares `supports_skills`; the frontend uses that contract to select compatible strategies.
