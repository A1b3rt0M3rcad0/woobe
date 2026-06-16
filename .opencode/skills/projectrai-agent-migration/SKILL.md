---
name: projectrai-agent-migration
description: Migrate ProjectRAI ai, knowledge, and runtime layers into src/modules/agent with shims, layer mapping, imports, routes, and bootstrap changes.
license: MIT
compatibility: opencode
metadata:
  project: ProjectRAI
  phase: migration
  scope: agent-bounded-context
---

# ProjectRAI Agent Migration

Use this skill for specs `010` through `045`, `130` through `133`, and legacy route/module migration work that consolidates `ai`, `knowledge`, and `runtime` into `src/modules/agent`.

The goal is not a mechanical rename. The goal is a bounded context migration: execution of agents, prompt composition, LLM integration, knowledge base usage, sessions, messages, releases, ask jobs, tools, event contracts, Outbox/Inbox, Unit of Work, and concrete workers become internal capabilities of `agent`.

## Target module structure

Use this structure unless the active spec says otherwise:

```text
src/modules/agent/
├── application/
│   ├── use_cases/
│   ├── dtos/
│   ├── handlers/
│   └── composers/
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── events.py
│   ├── enums.py
│   ├── errors.py
│   ├── repositories.py
│   └── services.py
├── infra/
│   ├── database/
│   │   ├── models.py
│   │   ├── repositories.py
│   │   ├── mappers.py
│   │   └── unit_of_work.py
│   ├── llm/
│   │   ├── langchain_factory.py
│   │   └── providers.py
│   ├── messaging/
│   │   ├── publishers.py
│   │   ├── consumers.py
│   │   └── event_mappers.py
│   └── workers/
│       ├── outbox_dispatcher.py
│       ├── inbox_consumer.py
│       ├── inbox_processor.py
│       └── registry.py
└── presentation/
    ├── controllers/
    ├── routes.py
    ├── schemas.py
    └── mappers.py
```

## Migration mapping

Treat the old modules as sources of capabilities:

- `ai`: LLM integration, provider configuration, prompt/model config, agent configuration, releases, AI-domain entities/contracts as applicable.
- `knowledge`: knowledge base, documents, chunks, retrieval/search, embeddings/vector-store integration, knowledge association to agents.
- `runtime`: sessions, messages, ask jobs, orchestration of agent execution, runtime use cases, previous ask flow.

Move by layer, not by convenience:

- Domain concepts go to `agent/domain`.
- Use cases, DTOs, handlers, and orchestration go to `agent/application`.
- Database models/repositories/UoW go to `agent/infra/database`.
- LLM providers/factories go to `agent/infra/llm`.
- Messaging adapters/mappers go to `agent/infra/messaging`.
- Concrete workers go to `agent/infra/workers`.
- FastAPI routes/schemas/controllers go to `agent/presentation`.

Do not put domain logic in `shared`, `src/workers`, or another module.

## Safe movement strategy

1. Read inventories first: files, imports, database ownership, routes, events, and workers.
2. Move or copy only the active layer specified by the active numbered spec.
3. Preserve public behavior with temporary shims when specs require compatibility.
4. Update imports from `modules.ai`, `modules.knowledge`, and `modules.runtime` to `modules.agent` only after the target exists and tests cover it.
5. Keep legacy modules until specs `140` through `145` explicitly deprecate/remove them.
6. Update runtime status after each spec.

## Shims and compatibility

A shim is allowed only when it:

- Delegates to `agent`.
- Has explicit deprecation intent.
- Has a removal spec.
- Has tests proving compatibility.
- Does not preserve the legacy module as an independent bounded context.

Do not add new behavior to legacy `ai`, `knowledge`, or `runtime` during migration. If behavior must change, implement it in `agent` and expose through the shim only when required.

## Routes and bootstrap

Final routes should converge on `/agent`. Legacy `/ai`, `/knowledge`, and `/runtime` routes may remain temporarily only as compatibility shims.

When updating bootstrap:

- Register `modules.agent.presentation.routes` as the target router.
- Remove direct registration of legacy routers only when the relevant shim/removal specs allow it.
- Update dependency injection bindings to agent-owned interfaces and implementations.
- Update settings/config names carefully; preserve environment compatibility through explicit deprecation when required.

## Import replacement rules

Do not perform global blind search-and-replace. For every import replacement:

1. Confirm the target symbol exists in `modules.agent`.
2. Confirm the importing layer is allowed to depend on that target layer.
3. Confirm no cross-module internal dependency is introduced.
4. Run focused tests for the affected path.

Use `rg` before and after:

```bash
rg "modules\.(ai|knowledge|runtime)" src tests || true
rg "from modules\.agent" src tests || true
```

## Acceptance checklist

A migration patch is acceptable only when:

- It matches the active spec's allowed changes.
- It does not move unrelated code.
- It preserves tests or adds spec-required tests.
- It preserves behavior unless the spec explicitly requires a behavior change.
- It updates runtime.
- It leaves a clear next spec.
