# Observability Module — Current-to-Canonical Migration Map

## Metadata

- **Module:** observability
- **Execution SHA:** `d929e89` (HEAD)
- **Date:** 2026-06-15
- **Total source files:** 29 (excluding `__pycache__`)
- **Detection tool:** `Get-ChildItem` (substitute for `find`), `Select-String` (substitute for `rg`)

## Current Structure

```
src/modules/observability/
├── __init__.py                    # Exports routes, registry
├── application/
│   ├── __init__.py                # Empty
│   └── composers/                 # 4 composers (create_trace, add_trace_event, get_trace, list_traces)
├── domain/
│   ├── __init__.py                # Docstring only
│   ├── entities.py                # Trace, TraceEvent
│   ├── enums.py                   # 2 StrEnum classes (TraceStatus, TraceEventType)
│   ├── errors.py                  # 1 domain error class (TraceNotFoundError)
│   └── repositories.py            # 2 abstract repository interfaces (TraceRepository, TraceEventRepository)
├── infra/
│   ├── __init__.py                # Docstring only
│   ├── models.py                  # 4 SQLAlchemy models (schema=observability): TraceModel,
│   │                                TraceEventModel, OutboxEventModel, InboxEventModel
│   ├── mappers.py                 # 4 mapper functions (entity↔model)
│   ├── repositories.py            # 2 SQLAlchemy repository impls + SQLAlchemyOutboxEventWriter
│   └── workers/
│       ├── __init__.py            # Docstring
│       └── registry.py            # ObservabilityWorkerRegistry (no workers registered)
├── presentation/
│   ├── __init__.py                # Docstring
│   ├── controllers/               # 4 controllers (create_trace, add_trace_event, get_trace, list_traces)
│   ├── routes.py                  # 4 routes on APIRouter(prefix="/observability")
│   └── schemas.py                 # 5 Pydantic models (CreateTraceRequest, CreateTraceEventRequest,
│                                    TraceResponse, TraceEventResponse, TraceDetailResponse)
└── service/
    ├── __init__.py                # Docstring
    ├── dtos.py                    # 6 DTO classes (CreateTraceInput, CreateTraceOutput, CreateTraceEventInput,
    │                                CreateTraceEventOutput, TraceEventResponse, TraceSummaryResponse,
    │                                TraceListItemResponse, ListTracesInput)
    └── use_cases.py               # 4 use case classes (CreateTraceUseCase, CreateTraceEventUseCase,
                                     GetTraceUseCase, ListTracesUseCase)
```

## Canonical Target Structure

```text
src/modules/observability/
├── application/
│   ├── composers/                 # Already exists (4 files) — keep
│   ├── dtos/                      # MOVE from service/dtos.py
│   ├── handlers/                  # CREATE (empty, future inbox handlers)
│   └── use_cases/                 # MOVE from service/use_cases.py
├── domain/
│   ├── __init__.py                # Keep
│   ├── entities.py                # Keep (2 entities)
│   ├── enums.py                   # Keep (2 enums)
│   ├── errors.py                  # Keep (1 error)
│   ├── events.py                  # CREATE (stub, extract from use_cases event_type strings)
│   ├── repositories.py            # Keep (2 interfaces)
│   ├── services.py                # CREATE (stub)
│   └── value_objects.py           # CREATE (stub)
├── infra/
│   ├── database/
│   │   ├── __init__.py            # CREATE
│   │   ├── models.py              # MOVE from infra/models.py
│   │   ├── mappers.py             # MOVE from infra/mappers.py
│   │   ├── repositories.py        # MOVE from infra/repositories.py
│   │   └── unit_of_work.py        # CREATE (ObservabilityUnitOfWork)
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
│       └── registry.py            # Keep (but will be enriched)
├── presentation/
│   ├── __init__.py                # Keep
│   ├── controllers/               # Keep (4 files)
│   ├── mappers.py                 # CREATE (stub, presentation-level mappers if needed)
│   ├── routes.py                  # Keep
│   └── schemas.py                 # Keep
```

## Layer-by-Layer Classification

### Domain Layer (src/modules/observability/domain/)

| File | Action | Notes |
|---|---|---|
| `__init__.py` | keep | Docstring only |
| `entities.py` | keep | 2 entities (Trace, TraceEvent) |
| `enums.py` | keep | 2 enums (TraceStatus, TraceEventType) |
| `errors.py` | keep | 1 error (TraceNotFoundError) |
| `repositories.py` | keep | 2 interfaces (TraceRepository, TraceEventRepository) |
| `events.py` | **create** | Stub; extract event_type strings from use_cases (`trace.created`, `trace_event.created`) |
| `services.py` | **create** | Stub |
| `value_objects.py` | **create** | Stub |

### Application Layer (src/modules/observability/application/)

| File | Action | Notes |
|---|---|---|
| `__init__.py` | keep | Empty |
| `composers/*.py` | keep | 4 composers already in application/composers/ |
| `dtos/__init__.py` | **create** | Package init with re-exports from service/dtos.py |
| `dtos/*.py` | **move** | From service/dtos.py |
| `use_cases/__init__.py` | **create** | Package init with re-exports from service/use_cases.py |
| `use_cases/*.py` | **move** | From service/use_cases.py |
| `handlers/__init__.py` | **create** | Empty init for future inbox handlers |

### Infrastructure Layer (src/modules/observability/infra/)

| File | Action | Notes |
|---|---|---|
| `__init__.py` | keep | Docstring |
| `models.py` | **move → infra/database/models.py** | Schema: observability. 4 models |
| `mappers.py` | **move → infra/database/mappers.py** | 4 mapper functions |
| `repositories.py` | **move → infra/database/repositories.py** | 2 SQLAlchemy repos + OutboxEventWriter |
| `workers/registry.py` | keep | Empty registry |
| `database/__init__.py` | **create** | Package init |
| `database/unit_of_work.py` | **create** | ObservabilityUnitOfWork |
| `messaging/__init__.py` | **create** | Package init |
| `messaging/consumers.py` | **create** | RabbitMQ consumer |
| `messaging/event_mappers.py` | **create** | Event serialization |
| `messaging/publishers.py` | **create** | RabbitMQ publisher |
| `workers/inbox_consumer.py` | **create** | Inbox consumer worker |
| `workers/inbox_processor.py` | **create** | Inbox processor worker |
| `workers/outbox_dispatcher.py` | **create** | Outbox dispatcher worker |

### Presentation Layer (src/modules/observability/presentation/)

| File | Action | Notes |
|---|---|---|
| `__init__.py` | keep | Docstring |
| `controllers/*.py` | keep | 4 controllers (import from service/dtos and service/use_cases — will be updated in spec 073) |
| `routes.py` | keep | 4 routes, prefix /observability |
| `schemas.py` | keep | 5 Pydantic models |
| `mappers.py` | **create** | Stub (presentation-level mappers) |

### Service Layer (src/modules/observability/service/) — to be removed

| File | Action | Notes |
|---|---|---|
| `__init__.py` | **→ delete** | After full application migration |
| `dtos.py` | **→ move to application/dtos/** | 8 DTO classes |
| `use_cases.py` | **→ move to application/use_cases/** | 4 use case classes |

## Cross-Module Foreign Keys

| Table | Column | References | Type |
|---|---|---|---|
| `observability.traces` | `project_id` | `core.projects.id` | cross-module (to be treated in spec 099) |
| `observability.traces` | `agent_id` | `ai.agents.id` | legacy schema (to be migrated) |
| `observability.traces` | `session_id` | `runtime.sessions.id` | legacy schema (to be migrated) |
| `observability.trace_events` | `project_id` | `core.projects.id` | cross-module (to be treated in spec 099) |

## Cross-Module Imports

- `modules.observability.domain.errors` → `shared.domain.errors` (allowed — technical dependency)
- `modules.observability.domain.repositories` → `shared.domain.objects` (allowed — technical dependency)
- `modules.observability.infra.models` → `shared.infra.database.base`, `shared.infra.database.inbox`, `shared.infra.database.outbox` (allowed)
- `modules.observability.infra.repositories` → `shared.infra.repositories.base_repository`, `shared.domain.events`, `shared.domain.objects`, `shared.infra.config.interface.unit_of_work` (allowed — technical contracts)
- `modules.observability.application.composers/*` → `shared.infra.database.postgres_unit_of_work`, `shared.application.transactional_handler` (allowed — technical contracts)

No imports from other domain modules found.

## Events

| Event Type | Source | Versioned |
|---|---|---|
| `trace.created` | `service/use_cases.py` (CreateTraceUseCase) | No |
| `trace_event.created` | `service/use_cases.py` (CreateTraceEventUseCase) | No |

Both events use unversioned event_type strings. To be standardized in transversal phase (specs 090-094).

## Routes

| Method | Path | Composer | Controller |
|---|---|---|---|
| GET | `/observability/traces` | list_traces_composer | ListTracesController |
| POST | `/observability/traces` | create_trace_composer | CreateTraceController |
| POST | `/observability/traces/{trace_id}/events` | add_trace_event_composer | AddTraceEventController |
| GET | `/observability/traces/{trace_id}` | get_trace_composer | GetTraceController |

## Workers

- `infra/workers/registry.py`: ObservabilityWorkerRegistry (empty — no workers registered)
- No concrete worker implementations exist.

## Tests

- No existing tests under `tests/modules/observability/`.
- No existing integration or contract tests for observability.

## Unit of Work

All 4 composers use `PostgresUnitOfWork` (generic). To be migrated to module-specific `ObservabilityUnitOfWork` in spec 076.

## Risks and Gaps

| Risk/Gap | Severity | Spec |
|---|---|---|
| 4 cross-module FKs (2 to core, 2 to legacy schemas) | critical | 099 |
| 4 composers use PostgresUnitOfWork (generic) | high | 076 |
| 2 unversioned event_type strings | high | 090-094 |
| No tests exist for observability | high | 078 |
| 2 legacy schema refs (ai.agents, runtime.sessions) | critical | 099 |
| Empty registry (no concrete workers) | high | 077 |
