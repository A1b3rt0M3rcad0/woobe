# Current to Target — Tools -> Agent

## Domain Layer

| Current (modules.tools) | Target (modules.agent) | Action | Notes |
|---|---|---|---|
| `domain/entities.py` (Tool, Secret) | `domain/entities.py` (merge into agent entities) | merge | Tool and Secret become agent domain entities |
| `domain/enums.py` (ToolType, RiskLevel, SecretType, ToolStatus) | `domain/enums.py` (merge) | merge | Enums become part of agent domain |
| `domain/errors.py` (ToolNotFoundError, SecretNotFoundError, DuplicateSecretError) | `domain/errors.py` (merge) | merge | Errors become agent domain errors |
| `domain/events.py` | `domain/events.py` (merge) | merge | Event definitions absorbed |
| `domain/repositories.py` (ToolRepository, SecretRepository ABCs) | `domain/repositories.py` (merge) | merge | Combined with agent repositories |
| `domain/services.py` | `domain/services.py` | merge | Empty; placeholder |
| `domain/value_objects.py` | `domain/value_objects.py` | merge | Empty; placeholder |

Note: Agent already has `domain/ports/tool_executor.py` (ToolExecutor ABC) and `domain/ports/tool_repository.py` (ToolRepository ABC). These ports coexist with the domain repository interfaces. The tools module's `ToolRepository` domain ABC and agent's port `ToolRepository` must be reconciled in spec 005.

## Application Layer

| Current (modules.tools) | Target (modules.agent) | Action | Notes |
|---|---|---|---|
| `application/dtos/tools_dtos.py` | `application/dtos/` (merge into agent dtos) | merge | 11 DTOs become agent DTOs |
| `application/use_cases/tools_use_cases.py` | `application/use_cases/` | merge | 8 use cases become agent use cases |
| `application/composers/*.py` (10 files) | `application/composers/` | merge | Composers become agent composers |
| `application/tool_converter.py` | `application/tool_converter.py` | merge | Agent already has this file from ai consolidation |

## Infrastructure — Database

| Current (modules.tools) | Target (modules.agent) | Action | Notes |
|---|---|---|---|
| `infra/database/models.py` (ToolModel, SecretModel, OutboxEventModel, InboxEventModel) | `infra/database/models.py` (merge) | merge | Agent models absorb tools models; schema changes to `agent` |
| `infra/database/mappers.py` (4 functions) | `infra/database/mappers.py` (merge) | merge | Mappers become part of agent mappers |
| `infra/database/repositories.py` (SQLAlchemyToolRepository, SQLAlchemySecretRepository, SQLAlchemyOutboxEventWriter) | `infra/database/repositories.py` | merge | Repositories added to AgentUnitOfWork |
| `infra/database/unit_of_work.py` (ToolsUnitOfWork) | `infra/database/unit_of_work.py` (AgentUnitOfWork) | merge | Tools repositories injected into AgentUnitOfWork. **No ToolsUnitOfWork retained.** |

## Infrastructure — Messaging

| Current (modules.tools) | Target (modules.agent) | Action | Notes |
|---|---|---|---|
| `infra/messaging/event_mappers.py` | `infra/messaging/event_mappers.py` | merge | Combined with agent event mappers |
| `infra/messaging/publishers.py` | `infra/messaging/publishers.py` | merge | Combined with agent publishers |
| `infra/messaging/consumers.py` | `infra/messaging/consumers.py` | merge | Combined with agent consumers |
| `infra/messaging/inbox_handlers.py` | `infra/messaging/inbox_handlers.py` | merge | Combined with agent inbox handlers |

## Infrastructure — Workers

| Current (modules.tools) | Target (modules.agent) | Action | Notes |
|---|---|---|---|
| `infra/workers/outbox_dispatcher.py` (ToolsOutboxDispatcherWorker) | `infra/workers/outbox_dispatcher.py` | merge | Combined with agent outbox dispatcher or kept separate |
| `infra/workers/inbox_consumer.py` (ToolsInboxConsumerWorker) | `infra/workers/inbox_consumer.py` | merge | Combined with agent inbox consumer |
| `infra/workers/inbox_processor.py` (ToolsInboxProcessorWorker) | `infra/workers/inbox_processor.py` | merge | Combined with agent inbox processor |
| `infra/workers/registry.py` (ToolsWorkerRegistry) | `infra/workers/registry.py` | merge | Workers registered in agent worker registry |

## Infrastructure — Adapters

| Target (modules.agent) | Current behavior | Future | Notes |
|---|---|---|---|
| `infra/adapters/tools_tool_executor.py` | Uses `importlib` to call `modules.tools` | Direct import of agent-owned use cases | Replaced after consolidation |
| `infra/adapters/tools_tool_repository.py` | Uses `importlib` to call `modules.tools` repos | Direct import of agent-owned repositories | Replaced after consolidation |

## Presentation

| Current (modules.tools) | Target (modules.agent) | Action | Notes |
|---|---|---|---|
| `presentation/routes.py` (prefix `/tools`) | `presentation/routes.py` (merge) | merge + shim | Routes added to agent router; `/tools` routes preserved via shim during cutover |
| `presentation/schemas.py` (9 schemas) | `presentation/schemas.py` (merge) | merge | Schemas absorbed into agent schemas |
| `presentation/mappers.py` | `presentation/mappers.py` (merge) | merge | Mappers absorbed |
| `presentation/controllers/*.py` (10 files) | `presentation/controllers/` (merge) | merge | Controllers absorbed into agent controllers |

## Key design decisions

1. **No `ToolsUnitOfWork`** — Tools repositories will be added as properties on `AgentUnitOfWork`
2. **No `tools` schema** — All tables migrate to `agent` schema (spec 011)
3. **No duplicate Outbox/Inbox** — Agent's outbox/inbox models absorb tools events
4. **Event renaming** — `tools.tool.*` and `tools.secret.*` events will be mapped/reconciled with agent event convention
5. **Shim period** — Legacy `/tools` routes remain functional via compatibility shims until cutover
6. **Capability organization** — Tools functions may be organized under `agent.tools` and `agent.tool_secrets` as capability sub-packages (layer-internal), without creating a separate bounded context or second UoW/Outbox
