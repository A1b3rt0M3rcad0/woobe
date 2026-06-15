# Tools Module — Current-to-Canonical Migration Map

## Metadata

- **Module:** tools
- **Execution SHA:** `210c95c` (HEAD)
- **Date:** 2026-06-15
- **Total source files:** 32 (excluding `__pycache__`)
- **Detection tool:** `Get-ChildItem` (substitute for `find`), `Select-String` (substitute for `rg`)

## Current Structure

```
src/modules/tools/
├── __init__.py                    # Exports routes, registry
├── application/
│   ├── __init__.py                # Empty
│   └── composers/                 # 10 composers (create_secret, create_tool,
│                                    delete_tool, execute_tool, list_secrets,
│                                    list_tools_by_agent, list_tools, test_tool,
│                                    update_tool, update_tool_status)
├── domain/
│   ├── __init__.py                # Re-exports entities, enums, errors, repositories
│   ├── entities.py                # Tool, Secret
│   ├── enums.py                   # 4 StrEnum classes (ToolType, RiskLevel, SecretType, ToolStatus)
│   ├── errors.py                  # 3 domain error classes
│   └── repositories.py            # 2 abstract repository interfaces (ToolRepository, SecretRepository)
├── infra/
│   ├── __init__.py                # Empty
│   ├── models.py                  # 4 SQLAlchemy models (schema=tools)
│   ├── mappers.py                 # 4 mapper functions
│   ├── repositories.py            # 3 SQLAlchemy repository impls + OutboxEventWriter
│   └── workers/
│       ├── __init__.py            # Empty
│       └── registry.py            # ToolsWorkerRegistry (no workers registered)
├── presentation/
│   ├── __init__.py                # Empty
│   ├── controllers/               # 10 controllers
│   ├── routes.py                  # 10 routes on APIRouter(prefix="/tools")
│   └── schemas.py                 # 9 Pydantic request/response schemas
└── service/
    ├── __init__.py                # Empty
    ├── dtos.py                    # 15 DTO classes (10 input + 5 output)
    ├── tool_converter.py          # OpenAI tool definition converter
    └── use_cases.py               # 10 use case classes
```

## Canonical Target Structure

```text
src/modules/tools/
├── application/
│   ├── composers/                 # Already exists (10 files) — keep
│   ├── dtos/                      # MOVE from service/dtos.py
│   ├── handlers/                  # CREATE (empty, future inbox handlers)
│   └── use_cases/                 # MOVE from service/use_cases.py
├── domain/
│   ├── __init__.py                # Keep
│   ├── entities.py                # Keep
│   ├── enums.py                   # Keep
│   ├── errors.py                  # Keep
│   ├── events.py                  # CREATE (stub, extract from use_cases event_type strings)
│   ├── repositories.py            # Keep
│   ├── services.py                # CREATE (stub, future domain services)
│   └── value_objects.py           # CREATE (stub, future value objects)
├── infra/
│   ├── database/
│   │   ├── __init__.py            # CREATE
│   │   ├── models.py              # MOVE from infra/models.py
│   │   ├── mappers.py             # MOVE from infra/mappers.py
│   │   ├── repositories.py        # MOVE from infra/repositories.py
│   │   └── unit_of_work.py        # CREATE (ToolsUnitOfWork)
│   ├── messaging/
│   │   ├── __init__.py            # CREATE
│   │   ├── consumers.py           # CREATE (RabbitMQ consumer)
│   │   ├── event_mappers.py       # CREATE (event serialization)
│   │   └── publishers.py          # CREATE (RabbitMQ publisher)
│   └── workers/
│       ├── __init__.py            # Keep
│       ├── inbox_consumer.py      # CREATE
│       ├── inbox_processor.py     # CREATE
│       ├── outbox_dispatcher.py   # CREATE
│       └── registry.py            # UPDATE (register workers)
└── presentation/
    ├── __init__.py                # Keep
    ├── controllers/               # Keep (10 files)
    ├── mappers.py                 # CREATE (presentation-level mappers, if needed)
    ├── routes.py                  # Keep
    └── schemas.py                 # Keep
```

## File-by-File Migration Plan

| # | Current Path | Action | Target Path | Notes |
|---|-------------|--------|-------------|-------|
| 1 | `__init__.py` | keep | `__init__.py` | Already canonical |
| 2 | `application/__init__.py` | keep | `application/__init__.py` | Empty |
| 3 | `application/composers/create_secret_composer.py` | keep + update | `application/composers/create_secret_composer.py` | Update imports to application/use_cases |
| 4 | `application/composers/create_tool_composer.py` | keep + update | `application/composers/create_tool_composer.py` | Update imports to application/use_cases |
| 5 | `application/composers/delete_tool_composer.py` | keep + update | `application/composers/delete_tool_composer.py` | Update imports to application/use_cases |
| 6 | `application/composers/execute_tool_composer.py` | keep + update | `application/composers/execute_tool_composer.py` | Update imports to application/use_cases |
| 7 | `application/composers/list_secrets_composer.py` | keep + update | `application/composers/list_secrets_composer.py` | Update imports to application/use_cases |
| 8 | `application/composers/list_tools_by_agent_composer.py` | keep + update | `application/composers/list_tools_by_agent_composer.py` | Update imports to application/use_cases |
| 9 | `application/composers/list_tools_composer.py` | keep + update | `application/composers/list_tools_composer.py` | Update imports to application/use_cases |
| 10 | `application/composers/test_tool_composer.py` | keep + update | `application/composers/test_tool_composer.py` | Update imports to application/use_cases |
| 11 | `application/composers/update_tool_composer.py` | keep + update | `application/composers/update_tool_composer.py` | Update imports to application/use_cases |
| 12 | `application/composers/update_tool_status_composer.py` | keep + update | `application/composers/update_tool_status_composer.py` | Update imports to application/use_cases |
| 13 | `domain/__init__.py` | keep | `domain/__init__.py` | Already canonical |
| 14 | `domain/entities.py` | keep | `domain/entities.py` | 2 entities, already canonical |
| 15 | `domain/enums.py` | keep | `domain/enums.py` | 4 enums, already canonical |
| 16 | `domain/errors.py` | keep | `domain/errors.py` | 3 errors, already canonical |
| 17 | `domain/repositories.py` | keep | `domain/repositories.py` | 2 ABC interfaces, already canonical |
| 18 | — | create | `domain/events.py` | Stub, event type constants from use_cases |
| 19 | — | create | `domain/services.py` | Stub |
| 20 | — | create | `domain/value_objects.py` | Stub |
| 21 | `infra/__init__.py` | keep (until cleanup) | `infra/__init__.py` | Remove when infra/database/ is stable |
| 22 | `infra/models.py` | move | `infra/database/models.py` | All 4 models |
| 23 | `infra/mappers.py` | move | `infra/database/mappers.py` | All 4 mapper functions |
| 24 | `infra/repositories.py` | move | `infra/database/repositories.py` | All 3 repository/outbox classes |
| 25 | — | create | `infra/database/unit_of_work.py` | ToolsUnitOfWork with repositories + outbox |
| 26 | — | create | `infra/database/__init__.py` | Package init |
| 27 | — | create | `infra/messaging/__init__.py` | Package init |
| 28 | — | create | `infra/messaging/event_mappers.py` | Outbox/Inbox event mappers |
| 29 | — | create | `infra/messaging/publishers.py` | ToolsRabbitMQPublisher |
| 30 | — | create | `infra/messaging/consumers.py` | ToolsRabbitMQConsumer |
| 31 | — | create | `infra/messaging/inbox_handlers.py` | Inbox event router |
| 32 | `infra/workers/__init__.py` | keep | `infra/workers/__init__.py` | Empty |
| 33 | — | create | `infra/workers/outbox_dispatcher.py` | ToolsOutboxDispatcherWorker |
| 34 | — | create | `infra/workers/inbox_consumer.py` | ToolsInboxConsumerWorker |
| 35 | — | create | `infra/workers/inbox_processor.py` | ToolsInboxProcessorWorker |
| 36 | `infra/workers/registry.py` | update | `infra/workers/registry.py` | Register workers |
| 37 | `presentation/__init__.py` | keep | `presentation/__init__.py` | Empty |
| 38 | `presentation/controllers/` (10 files) | keep + update | `presentation/controllers/*.py` | Update imports to application/ |
| 39 | — | create | `presentation/mappers.py` | Presentation mapper stub |
| 40 | `presentation/routes.py` | keep | `presentation/routes.py` | 10 routes, already canonical |
| 41 | `presentation/schemas.py` | keep | `presentation/schemas.py` | Already canonical |
| 42 | `service/__init__.py` | delete (after migration) | — | Legacy path |
| 43 | `service/dtos.py` | move | `application/dtos/` (split into individual files) | 15 DTOs |
| 44 | `service/use_cases.py` | move | `application/use_cases/` (split into individual files) | 10 use cases |
| 45 | `service/tool_converter.py` | move | `application/` or keep in service | 1 converter utility |

## Layer Classification

| Layer | Files | Status |
|-------|-------|--------|
| **Domain** | entities.py, enums.py, errors.py, repositories.py | Already canonical (4/7 files present; missing events.py, services.py, value_objects.py) |
| **Application** | 10 composers, service/dtos.py, service/use_cases.py, service/tool_converter.py | Partially canonical (composers OK; DTOs, use cases and converter in legacy service/) |
| **Infrastructure (Database)** | infra/models.py, infra/mappers.py, infra/repositories.py | Flat (needs infra/database/ subdirectory + unit_of_work) |
| **Infrastructure (Messaging)** | — | Missing entirely |
| **Infrastructure (Workers)** | infra/workers/registry.py | Missing dispatcher, inbox consumer, inbox processor |
| **Presentation** | routes.py, schemas.py, 10 controllers | Partially canonical (missing mappers.py; controllers import from service/) |

## Imports Summary

- **Cross-module imports:** NONE (production code only)
- **Shared imports:** `shared.domain.events.OutboxEventWriter`, `shared.infra.crypto`, `shared.infra.database.postgres_unit_of_work.PostgresUnitOfWork`, `shared.infra.database.base.BaseModel`, `shared.infra.database.inbox.InboxEventModel`, `shared.infra.database.outbox.OutboxEventModel`, `shared.infra.config.interface.unit_of_work.UnitOfWork`, `shared.infra.repositories.base_repository.BaseSQLAlchemyRepository`, `shared.domain.errors.ConflictError`, `shared.domain.errors.NotFoundError`, `shared.domain.objects.CursorPage`, `shared.presentation.http.adapter`, `shared.workers.contracts`, `shared.application.transactional_handler.TransactionalHandler`

## Database

- **Schema:** `tools`
- **Tables:** tools, secrets, outbox_events, inbox_events
- **Entities:** Tool, Secret
- **Cross-module FKs:** 3 (2 to `core.projects.id`, 1 legacy to `ai.agents.id`)
  - `tools.tools.project_id -> core.projects.id`
  - `tools.tools.agent_id -> ai.agents.id` (legacy, schema removed/renamed)
  - `tools.secrets.project_id -> core.projects.id`
- **Intra-module FKs:** NONE
- **Legacy schema refs (ai/knowledge/runtime):** 1 (`ai.agents.id` in tool model)

## Routes

| Method | Path | Controller | Use Case |
|--------|------|-----------|----------|
| GET | /tools/tools | ListToolsController | ListToolsUseCase |
| POST | /tools/tools | CreateToolController | CreateToolUseCase |
| PATCH | /tools/tools/{tool_id} | UpdateToolController | UpdateToolUseCase |
| PATCH | /tools/tools/{tool_id}/status | UpdateToolStatusController | UpdateToolStatusUseCase |
| DELETE | /tools/tools/{tool_id} | DeleteToolController | DeleteToolUseCase |
| POST | /tools/tools/test | TestToolController | TestToolUseCase |
| POST | /tools/tools/execute | ExecuteToolController | ExecuteToolUseCase |
| GET | /tools/agents/{agent_id}/tools | ListToolsByAgentController | ListToolsByAgentUseCase |
| GET | /tools/secrets | ListSecretsController | ListSecretsUseCase |
| POST | /tools/secrets | CreateSecretController | CreateSecretUseCase |

## Events (Unversioned)

| Event Type | Aggregate | Emitted By |
|-----------|-----------|-----------|
| tools.tool.created | Tool | CreateToolUseCase |
| tools.secret.created | Secret | CreateSecretUseCase |
| tools.tool.updated | Tool | UpdateToolUseCase |
| tools.tool.status_changed | Tool | UpdateToolStatusUseCase |

## Workers

- **Worker files:** 1 (`infra/workers/registry.py`)
- **Concrete workers:** 0 (registry is empty, no workers registered)
- **Existing workers needed:** ToolsOutboxDispatcherWorker, ToolsInboxConsumerWorker, ToolsInboxProcessorWorker

## Tests

- **Existing tools tests:** 0 (`tests/modules/tools/` does not exist)
- **Existing architecture tests:** pre-existing failures (unrelated)

## Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 3 cross-module FKs (2 to core, 1 legacy to ai) | high | Defer to spec 099 (expand-migrate-contract) |
| 10 composers use PostgresUnitOfWork | high | Defer to spec 086 (ToolsUnitOfWork) |
| Events are unversioned | medium | Defer to spec 090 (envelope standardization) |
| 0 existing tools tests | medium | Add in spec 088 (test phase) |
| Missing messaging/workers infrastructure | high | Create in spec 087 (messaging phase) |
| Legacy ai schema reference in tool.agent_id FK | critical | Defer to spec 099 (requires expand-migrate-contract) |
