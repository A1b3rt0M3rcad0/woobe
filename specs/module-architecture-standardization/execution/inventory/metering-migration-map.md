# Metering Module — Current-to-Canonical Migration Map

## Metadata

- **Module:** metering
- **Execution SHA:** `8897b1d` (HEAD)
- **Date:** 2026-06-15
- **Total source files:** 27 (excluding `__pycache__`)
- **Detection tool:** `Get-ChildItem` (substitute for `find`), `Select-String` (substitute for `rg`)

## Current Structure

```
src/modules/metering/
├── __init__.py                    # Exports routes, registry
├── application/
│   ├── __init__.py                # Empty
│   └── composers/                 # 3 composers (record_usage, get_agent_daily_usage, get_project_daily_usage)
├── domain/
│   ├── __init__.py                # Docstring only
│   ├── entities.py                # UsageEvent, UsageDailyProject, UsageDailyAgent
│   ├── enums.py                   # 2 StrEnum classes (UsageEventType, UsageUnit)
│   ├── errors.py                  # 1 domain error class (UsageEventNotFoundError)
│   └── repositories.py            # 3 abstract repository interfaces
├── infra/
│   ├── __init__.py                # Docstring only
│   ├── models.py                  # 5 SQLAlchemy models (schema=metering): UsageEventModel,
│   │                                UsageDailyProjectModel, UsageDailyAgentModel,
│   │                                OutboxEventModel, InboxEventModel
│   ├── mappers.py                 # 6 mapper functions (entity↔model)
│   ├── repositories.py            # 3 SQLAlchemy repository impls + SQLAlchemyOutboxEventWriter
│   └── workers/
│       ├── __init__.py            # Docstring
│       └── registry.py            # MeteringWorkerRegistry (no workers registered)
├── presentation/
│   ├── __init__.py                # Docstring
│   ├── controllers/               # 3 controllers (record_usage, get_agent_daily_usage, get_project_daily_usage)
│   ├── routes.py                  # 3 routes on APIRouter(prefix="/metering")
│   └── schemas.py                 # 3 Pydantic models (RecordUsageRequest, UsageEventResponse, DailyUsageResponse)
└── service/
    ├── __init__.py                # Docstring
    ├── dtos.py                    # 3 DTO classes (RecordUsageInput, RecordUsageOutput, DailyUsageResponse)
    └── use_cases.py               # 3 use case classes (RecordUsageUseCase, GetProjectDailyUsageUseCase, GetAgentDailyUsageUseCase)
```

## Canonical Target Structure

```text
src/modules/metering/
├── application/
│   ├── composers/                 # Already exists (3 files) — keep
│   ├── dtos/                      # MOVE from service/dtos.py
│   ├── handlers/                  # CREATE (empty, future inbox handlers)
│   └── use_cases/                 # MOVE from service/use_cases.py
├── domain/
│   ├── __init__.py                # Keep
│   ├── entities.py                # Keep (3 entities)
│   ├── enums.py                   # Keep (2 enums)
│   ├── errors.py                  # Keep (1 error)
│   ├── events.py                  # CREATE (stub, extract from use_cases event_type strings)
│   ├── repositories.py            # Keep (3 interfaces)
│   ├── services.py                # CREATE (stub)
│   └── value_objects.py           # CREATE (stub)
├── infra/
│   ├── database/
│   │   ├── __init__.py            # CREATE
│   │   ├── models.py              # MOVE from infra/models.py
│   │   ├── mappers.py             # MOVE from infra/mappers.py
│   │   ├── repositories.py        # MOVE from infra/repositories.py
│   │   └── unit_of_work.py        # CREATE (MeteringUnitOfWork)
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
    ├── controllers/               # UPDATE (import from application/ instead of service/)
    ├── mappers.py                 # CREATE (if needed, or keep in presentation)
    ├── routes.py                  # Keep (3 routes, prefix /metering)
    └── schemas.py                 # Keep (3 models)
```

## File-by-File Classification

### Domain Layer

| Current Path | Target Path | Action | Layer | Category |
|---|---|---|---|---|
| `src/modules/metering/domain/__init__.py` | same | keep | domain | init |
| `src/modules/metering/domain/entities.py` | same | keep | domain | 3 entities |
| `src/modules/metering/domain/enums.py` | same | keep | domain | 2 enums |
| `src/modules/metering/domain/errors.py` | same | keep | domain | 1 error |
| `src/modules/metering/domain/repositories.py` | same | keep | domain | 3 abstract repos |
| — | `src/modules/metering/domain/events.py` | create | domain | stub |
| — | `src/modules/metering/domain/services.py` | create | domain | stub |
| — | `src/modules/metering/domain/value_objects.py` | create | domain | stub |

### Application Layer

| Current Path | Target Path | Action | Layer | Category |
|---|---|---|---|---|
| `src/modules/metering/application/__init__.py` | same | keep | application | init |
| `src/modules/metering/application/composers/__init__.py` | same | keep | application | init |
| `src/modules/metering/application/composers/record_usage_composer.py` | same | update | application | composer (uses PostgresUnitOfWork, imports service/use_cases) |
| `src/modules/metering/application/composers/get_agent_daily_usage_composer.py` | same | update | application | composer (uses PostgresUnitOfWork, imports service/use_cases) |
| `src/modules/metering/application/composers/get_project_daily_usage_composer.py` | same | update | application | composer (uses PostgresUnitOfWork, imports service/use_cases) |
| — | `src/modules/metering/application/dtos/__init__.py` | create | application | init |
| `src/modules/metering/service/dtos.py` | `src/modules/metering/application/dtos/` | move | application | 3 DTOs |
| — | `src/modules/metering/application/use_cases/__init__.py` | create | application | init |
| `src/modules/metering/service/use_cases.py` | `src/modules/metering/application/use_cases/` | move | application | 3 use cases |
| — | `src/modules/metering/application/handlers/__init__.py` | create | application | init |

### Infrastructure Layer — Database

| Current Path | Target Path | Action | Layer | Category |
|---|---|---|---|---|
| — | `src/modules/metering/infra/database/__init__.py` | create | infra | init |
| `src/modules/metering/infra/models.py` | `src/modules/metering/infra/database/models.py` | move | infra | 5 models |
| `src/modules/metering/infra/mappers.py` | `src/modules/metering/infra/database/mappers.py` | move | infra | 6 mappers |
| `src/modules/metering/infra/repositories.py` | `src/modules/metering/infra/database/repositories.py` | move | infra | 3 repos + OutboxEventWriter |
| — | `src/modules/metering/infra/database/unit_of_work.py` | create | infra | MeteringUnitOfWork |

### Infrastructure Layer — Messaging

| Current Path | Target Path | Action | Layer | Category |
|---|---|---|---|---|
| — | `src/modules/metering/infra/messaging/__init__.py` | create | infra | init |
| — | `src/modules/metering/infra/messaging/consumers.py` | create | infra | RabbitMQ consumer |
| — | `src/modules/metering/infra/messaging/event_mappers.py` | create | infra | event serialization |
| — | `src/modules/metering/infra/messaging/publishers.py` | create | infra | RabbitMQ publisher |

### Infrastructure Layer — Workers

| Current Path | Target Path | Action | Layer | Category |
|---|---|---|---|---|
| `src/modules/metering/infra/workers/__init__.py` | same | keep | infra | init |
| `src/modules/metering/infra/workers/registry.py` | same | update | infra | registry (currently empty, stub) |
| — | `src/modules/metering/infra/workers/inbox_consumer.py` | create | infra | worker |
| — | `src/modules/metering/infra/workers/inbox_processor.py` | create | infra | worker |
| — | `src/modules/metering/infra/workers/outbox_dispatcher.py` | create | infra | worker |

### Presentation Layer

| Current Path | Target Path | Action | Layer | Category |
|---|---|---|---|---|
| `src/modules/metering/presentation/__init__.py` | same | keep | presentation | init |
| `src/modules/metering/presentation/controllers/__init__.py` | same | keep | presentation | init |
| `src/modules/metering/presentation/controllers/record_usage_controller.py` | same | update | presentation | imports from service/use_cases |
| `src/modules/metering/presentation/controllers/get_agent_daily_usage_controller.py` | same | update | presentation | imports from service/use_cases |
| `src/modules/metering/presentation/controllers/get_project_daily_usage_controller.py` | same | update | presentation | imports from service/use_cases |
| `src/modules/metering/presentation/routes.py` | same | keep | presentation | 3 routes, prefix /metering |
| `src/modules/metering/presentation/schemas.py` | same | keep | presentation | 3 models |
| — | `src/modules/metering/presentation/mappers.py` | create | presentation | optional (presentation-level mapping) |

## Cross-Module Foreign Keys

| Source Table | Column | Referenced Table | Type |
|---|---|---|---|
| `metering.usage_events` | `project_id` | `core.projects.id` | cross-module (deferred to spec 099) |
| `metering.usage_events` | `agent_id` | `ai.agents.id` | cross-module LEGACY (deferred to spec 099) |
| `metering.usage_daily_project` | `project_id` | `core.projects.id` | cross-module (deferred to spec 099) |
| `metering.usage_daily_agent` | `agent_id` | `ai.agents.id` | cross-module LEGACY (deferred to spec 099) |
| `metering.usage_daily_agent` | `project_id` | `core.projects.id` | cross-module (deferred to spec 099) |

## Routes

| Method | Path | Controller | Composer | Use Case |
|---|---|---|---|---|
| POST | `/metering/usage-events` | RecordUsageController | record_usage_composer | RecordUsageUseCase |
| GET | `/metering/projects/{project_id}/daily` | GetProjectDailyUsageController | get_project_daily_usage_composer | GetProjectDailyUsageUseCase |
| GET | `/metering/agents/{agent_id}/daily` | GetAgentDailyUsageController | get_agent_daily_usage_composer | GetAgentDailyUsageUseCase |

## Events

| event_type string | Versioned? | Outbox Source | Inbox Target |
|---|---|---|---|
| `usage_event.recorded` | No | RecordUsageUseCase | — |

## Workers

| Worker | Exists? | Registry | Notes |
|---|---|---|---|
| OutboxDispatcher | No | MeteringWorkerRegistry (empty) | Must create |
| InboxConsumer | No | MeteringWorkerRegistry (empty) | Must create |
| InboxProcessor | No | MeteringWorkerRegistry (empty) | Must create |

## Tests

| Test File | Exists? | Type |
|---|---|---|
| `tests/unit/test_metering/test_entities.py` | Yes | pre-existing unit |
| `tests/unit/test_metering/test_enums.py` | Yes | pre-existing unit |
| `tests/unit/test_metering/test_errors.py` | Yes | pre-existing unit |
| `tests/unit/test_metering/test_dtos.py` | Yes | pre-existing unit (imports from service/) |
| `tests/unit/test_metering/test_use_cases.py` | Yes | pre-existing unit (imports from domain) |

## Gaps vs Canonical Structure

1. `infra/database/` directory does not exist — models/mappers/repositories are flat under `infra/`
2. `infra/messaging/` directory does not exist — no consumers, publishers, or event_mappers
3. `application/dtos/` does not exist — DTOs are in `service/dtos.py`
4. `application/use_cases/` does not exist — use cases are in `service/use_cases.py`
5. `application/handlers/` does not exist
6. `domain/events.py` does not exist (event types are hardcoded strings in use_cases)
7. `domain/services.py` and `domain/value_objects.py` do not exist
8. No module-specific UnitOfWork — all 3 composers use `PostgresUnitOfWork`
9. No workers except empty registry — outbox dispatcher, inbox consumer/processor missing
10. Controllers import from `service/` instead of `application/use_cases/`
11. No presentation `mappers.py`

## Risks and Order

| Risk | Severity | Mitigation | Spec |
|---|---|---|---|
| 3 cross-module FKs (2 to ai.agents, 1 to core.projects) | critical | expand-migrate-contract + IDs opacos (spec 099) | 099 |
| 3 composers use PostgresUnitOfWork | alta | MeteringUnitOfWork (spec 066) | 066 |
| All 3 controllers import from service/ | alta | migrate to application/ (spec 063) | 063 |
| No messaging infrastructure | alta | create consumers/publishers/event_mappers (spec 067) | 067 |
| No workers (empty registry) | alta | create outbox_dispatcher, inbox_consumer, inbox_processor (spec 067) | 067 |
| Events unversioned | alta | versioned envelope (spec 090) | 090 |
| Legacy FK to ai.agents | crítica | migrate to agent.agents (spec 099) | 099 |

## Internal Execution Order

| Step | Spec | Action |
|---|---|---|
| 1 | 061 | Create canonical skeleton (directories + stubs) |
| 2 | 062 | Validate domain layer (already canonical; add entity tests + arch tests) |
| 3 | 063 | Migrate service/ → application/ (DTOs, use cases, update composers/controllers, shims) |
| 4 | 064 | Normalize presentation layer (controller tests, route tests) |
| 5 | 065 | Move infra/ → infra/database/ (models, mappers, repositories, shims, update env.py) |
| 6 | 066 | Create MeteringUnitOfWork; migrate composers from PostgresUnitOfWork |
| 7 | 067 | Create messaging infrastructure (consumers, publishers, event_mappers, inbox_handlers) |
| 8 | 067 | Create workers (outbox_dispatcher, inbox_consumer, inbox_processor, update registry) |
| 9 | 068 | Add comprehensive test suite (enums, errors, repos, DTOs, routes, schemas, event mappers) |
| 10 | 069 | Remove legacy paths and temporary shims (service/ + infra/*.py flat files) |
