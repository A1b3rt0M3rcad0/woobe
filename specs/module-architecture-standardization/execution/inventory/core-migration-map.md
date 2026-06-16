# Core Module — Current-to-Canonical Migration Map

## Metadata

- **Module:** core
- **Execution SHA:** `fd5f87c` (HEAD)
- **Date:** 2026-06-15
- **Total source files:** 33
- **Detection tool:** `Get-ChildItem` (substitute for `find`), `Select-String` (substitute for `rg`)

## Current Structure

```
src/modules/core/
├── __init__.py                    # Exports routes
├── application/
│   ├── __init__.py                # Empty
│   ├── composers/                 # 6 composers (create_api_key, create_project, get_project, list_api_keys, list_projects, update_project)
│   └── dependencies.py            # Shared dependencies
├── domain/
│   ├── __init__.py                # Docstring only
│   ├── entities.py                # Project, ApiKey
│   ├── enums.py                   # 3 StrEnum classes
│   ├── errors.py                  # 3 domain error classes
│   └── repositories.py            # 2 abstract repository interfaces
├── infra/
│   ├── __init__.py                # Empty
│   ├── models.py                  # 4 SQLAlchemy models (schema=core)
│   ├── mappers.py                 # 4 mapper functions
│   └── repositories.py            # 2 SQLAlchemy repository impls + OutboxEventWriter
├── presentation/
│   ├── __init__.py                # Empty
│   ├── controllers/               # 6 controllers
│   ├── mappers.py                 # Presentation mappers
│   ├── routes.py                  # 6 routes on APIRouter(prefix="/core")
│   └── schemas.py                 # 5 Pydantic request/response models
└── service/
    ├── __init__.py                # Docstring only
    ├── dtos.py                    # 7 DTO classes (3 input + 4 output)
    └── use_cases.py               # 6 use case classes
```

## Canonical Target Structure

```text
src/modules/core/
├── application/
│   ├── composers/                 # Already exists (6 files) — keep
│   ├── dtos/                      # MOVE from service/dtos.py
│   ├── handlers/                  # CREATE (empty, future inbox handlers)
│   └── use_cases/                 # MOVE from service/use_cases.py
├── domain/
│   ├── entities.py                # Already exists — keep
│   ├── enums.py                   # Already exists — keep
│   ├── errors.py                  # Already exists — keep
│   ├── events.py                  # CREATE (domain event classes)
│   ├── repositories.py            # Already exists — keep
│   ├── services.py                # CREATE (stub, future domain services)
│   └── value_objects.py           # CREATE (stub, future VOs)
├── infra/
│   ├── database/
│   │   ├── mappers.py             # MOVE from infra/mappers.py
│   │   ├── models.py              # MOVE from infra/models.py
│   │   ├── repositories.py        # MOVE from infra/repositories.py
│   │   └── unit_of_work.py        # CREATE (future CoreUnitOfWork)
│   ├── messaging/
│   │   ├── consumers.py           # CREATE (future RabbitMQ consumer)
│   │   ├── event_mappers.py       # CREATE (future event mapping)
│   │   └── publishers.py          # CREATE (future event publishing)
│   └── workers/
│       ├── inbox_consumer.py      # CREATE (future inbox consumer worker)
│       ├── inbox_processor.py     # CREATE (future inbox processor worker)
│       ├── outbox_dispatcher.py   # CREATE (future outbox dispatcher worker)
│       └── registry.py            # CREATE (future worker registry)
└── presentation/
    ├── controllers/               # Already exists — keep
    ├── mappers.py                 # Already exists — keep
    ├── routes.py                  # Already exists — keep (imports from application/composers)
    └── schemas.py                 # Already exists — keep
```

## Per-File Classification

| # | Current Path | Action | Canonical Path | Layer |
|---|---|---|---|---|---|
| 1 | `__init__.py` | keep | `__init__.py` | module root |
| 2 | `application/__init__.py` | keep | `application/__init__.py` | application |
| 3 | `application/composers/__init__.py` | keep | `application/composers/__init__.py` | application |
| 4 | `application/composers/create_api_key_composer.py` | update | `application/composers/create_api_key_composer.py` | application |
| 5 | `application/composers/create_project_composer.py` | update | `application/composers/create_project_composer.py` | application |
| 6 | `application/composers/get_project_composer.py` | update | `application/composers/get_project_composer.py` | application |
| 7 | `application/composers/list_api_keys_composer.py` | update | `application/composers/list_api_keys_composer.py` | application |
| 8 | `application/composers/list_projects_composer.py` | update | `application/composers/list_projects_composer.py` | application |
| 9 | `application/composers/update_project_composer.py` | update | `application/composers/update_project_composer.py` | application |
| 10 | `application/dependencies.py` | keep | `application/dependencies.py` | application |
| 11 | `domain/__init__.py` | keep | `domain/__init__.py` | domain |
| 12 | `domain/entities.py` | keep | `domain/entities.py` | domain |
| 13 | `domain/enums.py` | keep | `domain/enums.py` | domain |
| 14 | `domain/errors.py` | keep | `domain/errors.py` | domain |
| 15 | `domain/repositories.py` | keep | `domain/repositories.py` | domain |
| 16 | `infra/__init__.py` | keep | `infra/__init__.py` | infra |
| 17 | `infra/mappers.py` | move | `infra/database/mappers.py` | infra/database |
| 18 | `infra/models.py` | move | `infra/database/models.py` | infra/database |
| 19 | `infra/repositories.py` | move | `infra/database/repositories.py` | infra/database |
| 20 | `presentation/__init__.py` | keep | `presentation/__init__.py` | presentation |
| 21 | `presentation/controllers/__init__.py` | keep | `presentation/controllers/__init__.py` | presentation |
| 22 | `presentation/controllers/create_api_key_controller.py` | update | `presentation/controllers/create_api_key_controller.py` | presentation |
| 23 | `presentation/controllers/create_project_controller.py` | update | `presentation/controllers/create_project_controller.py` | presentation |
| 24 | `presentation/controllers/get_project_controller.py` | update | `presentation/controllers/get_project_controller.py` | presentation |
| 25 | `presentation/controllers/list_api_keys_controller.py` | update | `presentation/controllers/list_api_keys_controller.py` | presentation |
| 26 | `presentation/controllers/list_projects_controller.py` | update | `presentation/controllers/list_projects_controller.py` | presentation |
| 27 | `presentation/controllers/update_project_controller.py` | update | `presentation/controllers/update_project_controller.py` | presentation |
| 28 | `presentation/mappers.py` | keep | `presentation/mappers.py` | presentation |
| 29 | `presentation/routes.py` | keep | `presentation/routes.py` | presentation |
| 30 | `presentation/schemas.py` | keep | `presentation/schemas.py` | presentation |
| 31 | `service/__init__.py` | shim | `service/__init__.py` | service (legacy) |
| 32 | `service/dtos.py` | move → shim | `application/dtos/` | application |
| 33 | `service/use_cases.py` | move → shim | `application/use_cases/` | application |

## Entities and Tables

- **Entities:** Project, ApiKey
- **Tables:** core.projects, core.api_keys, core.outbox_events, core.inbox_events
- **Cross-module FKs:** 
  - `core.projects.organization_id` → `identity.organizations.id`
  - `core.api_keys.created_by_user_id` → `identity.users.id`
- **Intra-module FKs:**
  - `core.api_keys.project_id` → `core.projects.id`
- **Schema:** `core` (PostgreSQL schema)

## Routes (preserve)

| Method | Path | Composer | Controller |
|---|---|---|---|
| GET | /core/projects | list_projects_composer | ListProjectsController |
| POST | /core/projects | create_project_composer | CreateProjectController |
| GET | /core/projects/{project_id} | get_project_composer | GetProjectController |
| PATCH | /core/projects/{project_id} | update_project_composer | UpdateProjectController |
| POST | /core/projects/{project_id}/api-keys | create_api_key_composer | CreateApiKeyController |
| GET | /core/projects/{project_id}/api-keys | list_api_keys_composer | ListApiKeysController |

## Events

| Event Type | Producer | Status |
|---|---|---|
| project.created | CreateProjectUseCase | Unversioned |
| project.updated | UpdateProjectUseCase | Unversioned |
| api_key.created | CreateApiKeyUseCase | Unversioned |

## Workers

No workers directory exists yet. No registry. Planned for spec 047.

## UoW

All 6 composers use `PostgresUnitOfWork` (generic). No core-specific UoW exists yet (planned for spec 046).

## Import Analysis

- **service/use_cases.py** depends on: domain entities/enums/errors/repositories, service/dtos, shared.domain.events (OutboxEventWriter)
- **Domain** imports: Python stdlib, uuid6, domain.enums, shared.domain.errors, shared.domain.objects (CursorPage)
- **Infra** imports: domain entities/enums/repositories, SQLAlchemy, infra mappers/models, shared.domain.events/objects, shared.infra.config.interface.unit_of_work, shared.infra.repositories.base_repository
- **Presentation** imports: service/dtos, service/use_cases, shared.presentation interface classes
- **Composers** import: service/use_cases, infra/repositories, PostgresUnitOfWork, shared.application TransactionalHandler, shared.infra.database.postgres_unit_of_work

## Migration Risks

| Risk | Severity | Mitigation |
|---|---|---|
| 6 composers import from `service/` | high | Spec 043 creates shims before removing service imports |
| 6 controllers import from `service/` | high | Spec 043 updates controller imports |
| PostgresUnitOfWork in all composers | high | Deferred to spec 046 |
| No existing unit tests for core | medium | Specs 042-044 create first tests |
| Cross-module FK to identity (organization_id, created_by_user_id) | high | Deferred to spec 099 |
| infra/mappers.py, models.py, repositories.py at flat infra/ instead of infra/database/ | medium | Spec 045 moves to infra/database/ |
