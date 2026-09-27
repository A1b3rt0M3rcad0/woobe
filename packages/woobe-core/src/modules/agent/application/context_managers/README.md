# Context Managers

This package contains the concrete programmable Context Manager algorithms used by Agent execution.

The stable boundary lives in:

```text
modules/agent/application/interfaces/context_assembler.py
```

Despite the historical `ContextAssembler` type name, the interface represents the complete Context Manager surface:

```text
inspect(...)
compact(...)
assemble(...)
```

Execution code depends only on that interface. A Context Manager decides how Context is inspected, compacted, summarized, trimmed, replaced, ordered, deduplicated and assembled. Runtime provides mechanisms such as model-assisted summarization, instrumentation and persistence; it does not own Context policy.

## Identity

Context Managers are identified only by name.

```text
stdcm
adaptive
hierarchical
memory-first
```

There are no Context Manager version suffixes and no `default` alias. If a different behavior must coexist as a separately selectable manager, give it a different name.

Agent and Release runtime config stores only:

```json
{
  "context_assembler": {
    "name": "stdcm"
  }
}
```

`WOOBE_DEFAULT_CONTEXT_MANAGER` is also a plain registered name:

```text
WOOBE_DEFAULT_CONTEXT_MANAGER=stdcm
```

## Add a built-in Context Manager

1. Create a manager module under this package.
2. Implement the structural `ContextAssembler` contract.
3. Choose a unique stable name such as `adaptive`.
4. Add backend-owned `ContextAssemblerDescriptor` metadata in `context_assembler_registry.py`.
5. Register the manager in `_register_builtin_context_managers(...)`.
6. Add focused manager and registry tests.

Example:

```python
class AdaptiveContextManager:
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

## Runtime rules

- Do not import concrete Context Managers from `infra/execution`.
- Do not add manager-specific branches to Agent Runtime invocation paths.
- Keep per-invocation mutable state inside request/local call scope.
- Runtime may share one manager instance across concurrent Runs.
- Context Managers may use only explicitly supplied Runtime capabilities.
- Context Managers do not own general Agent execution, Tool execution, Run lifecycle, Knowledge storage or Network orchestration.

## Built-in manager

```text
stdcm
└── StandardSkillsContextAssembler
    └── StandardContextAssembler
```

`stdcm` is the built-in Standard Context Manager and the system default. It supports Skills, pressure inspection, model-assisted summarize-and-replace compaction, deterministic budgeting, ordering, deduplication, provenance and final Context materialization.

Alternative algorithms use different names.

See [Agent Skills](../../../../../../../docs/skills/README.md) for Skill package and runtime contracts.
