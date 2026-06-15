# Billing Module — Current-to-Canonical Migration Map

## Metadata

- **Module:** billing
- **Execution SHA:** `c11c055` (HEAD)
- **Date:** 2026-06-15
- **Total source files:** 46 (excluding `__pycache__`)
- **Detection tool:** `Get-ChildItem` (substitute for `find`), `Select-String` (substitute for `rg`)

## Current Structure

```
src/modules/billing/
├── __init__.py                    # Exports routes, registry
├── application/
│   ├── __init__.py                # Empty
│   └── composers/                 # 4 composers (create_plan, create_subscription,
│                                    get_organization_subscription, list_plans)
├── domain/
│   ├── __init__.py                # Docstring only
│   ├── entities.py                # Plan, Customer, Subscription, PaymentEvent
│   ├── enums.py                   # 5 StrEnum classes
│   ├── errors.py                  # 3 domain error classes
│   └── repositories.py            # 4 abstract repository interfaces
├── infra/
│   ├── __init__.py                # Empty
│   ├── models.py                  # 6 SQLAlchemy models (schema=billing)
│   ├── mappers.py                 # 8 mapper functions
│   ├── repositories.py            # 4 SQLAlchemy repository impls + OutboxEventWriter
│   └── workers/
│       ├── __init__.py            # Empty
│       └── registry.py            # BillingWorkerRegistry (no workers registered)
├── presentation/
│   ├── __init__.py                # Empty
│   ├── controllers/               # 4 controllers
│   ├── routes.py                  # 4 routes on APIRouter(prefix="/billing")
│   └── schemas.py                 # 4 Pydantic request/response models
└── service/
    ├── __init__.py                # Docstring only
    ├── dtos.py                    # 8 DTO classes (5 input + 3 output)
    └── use_cases.py               # 6 use case classes
```

## Canonical Target Structure

```text
src/modules/billing/
├── application/
│   ├── composers/                 # Already exists (4 files) — keep
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
│   │   └── unit_of_work.py        # CREATE (BillingUnitOfWork)
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
    ├── controllers/               # Keep (4 files)
    ├── mappers.py                 # CREATE (presentation-level mappers, if needed)
    ├── routes.py                  # Keep
    └── schemas.py                 # Keep
```

## File-by-File Migration Plan

| # | Current Path | Action | Target Path | Notes |
|---|-------------|--------|-------------|-------|
| 1 | `__init__.py` | keep | `__init__.py` | Already canonical |
| 2 | `application/__init__.py` | keep | `application/__init__.py` | Empty |
| 3 | `application/composers/create_plan_composer.py` | keep + update | `application/composers/create_plan_composer.py` | Update imports to application/use_cases |
| 4 | `application/composers/create_subscription_composer.py` | keep + update | `application/composers/create_subscription_composer.py` | Update imports to application/use_cases |
| 5 | `application/composers/get_organization_subscription_composer.py` | keep + update | `application/composers/get_organization_subscription_composer.py` | Update imports to application/use_cases |
| 6 | `application/composers/list_plans_composer.py` | keep + update | `application/composers/list_plans_composer.py` | Update imports to application/use_cases |
| 7 | `domain/__init__.py` | keep | `domain/__init__.py` | Docstring only |
| 8 | `domain/entities.py` | keep | `domain/entities.py` | 4 entities, already canonical |
| 9 | `domain/enums.py` | keep | `domain/enums.py` | 5 enums, already canonical |
| 10 | `domain/errors.py` | keep | `domain/errors.py` | 3 errors, already canonical |
| 11 | `domain/repositories.py` | keep | `domain/repositories.py` | 4 ABC interfaces, already canonical |
| 12 | — | create | `domain/events.py` | Stub, event type constants from use_cases |
| 13 | — | create | `domain/services.py` | Stub |
| 14 | — | create | `domain/value_objects.py` | Stub |
| 15 | `infra/__init__.py` | keep (until cleanup) | `infra/__init__.py` | Remove when infra/database/ is stable |
| 16 | `infra/models.py` | move | `infra/database/models.py` | All 6 models |
| 17 | `infra/mappers.py` | move | `infra/database/mappers.py` | All 8 mapper functions |
| 18 | `infra/repositories.py` | move | `infra/database/repositories.py` | All 5 repository/outbox classes |
| 19 | — | create | `infra/database/unit_of_work.py` | BillingUnitOfWork with repositories + outbox |
| 20 | — | create | `infra/database/__init__.py` | Package init |
| 21 | — | create | `infra/messaging/__init__.py` | Package init |
| 22 | — | create | `infra/messaging/event_mappers.py` | Outbox/Inbox event mappers |
| 23 | — | create | `infra/messaging/publishers.py` | BillingRabbitMQPublisher |
| 24 | — | create | `infra/messaging/consumers.py` | BillingRabbitMQConsumer |
| 25 | — | create | `infra/messaging/inbox_handlers.py` | Inbox event router |
| 26 | `infra/workers/__init__.py` | keep | `infra/workers/__init__.py` | Empty |
| 27 | — | create | `infra/workers/outbox_dispatcher.py` | BillingOutboxDispatcherWorker |
| 28 | — | create | `infra/workers/inbox_consumer.py` | BillingInboxConsumerWorker |
| 29 | — | create | `infra/workers/inbox_processor.py` | BillingInboxProcessorWorker |
| 30 | `infra/workers/registry.py` | update | `infra/workers/registry.py` | Register workers |
| 31 | `presentation/__init__.py` | keep | `presentation/__init__.py` | Empty |
| 32 | `presentation/controllers/` (4 files) | keep + update | `presentation/controllers/*.py` | Update imports to application/ |
| 33 | — | create | `presentation/mappers.py` | Presentation mapper stub |
| 34 | `presentation/routes.py` | keep | `presentation/routes.py` | 4 routes, already canonical |
| 35 | `presentation/schemas.py` | keep | `presentation/schemas.py` | Already canonical |
| 36 | `service/__init__.py` | delete (after migration) | — | Legacy path |
| 37 | `service/dtos.py` | move | `application/dtos/` (split into individual files) | 8 DTOs |
| 38 | `service/use_cases.py` | move | `application/use_cases/` (split into individual files) | 6 use cases |

## Layer Classification

| Layer | Files | Status |
|-------|-------|--------|
| **Domain** | entities.py, enums.py, errors.py, repositories.py | Already canonical (4/7 files present; missing events.py, services.py, value_objects.py) |
| **Application** | 4 composers, service/dtos.py, service/use_cases.py | Partially canonical (composers OK; DTOs and use cases in legacy service/) |
| **Infrastructure (Database)** | infra/models.py, infra/mappers.py, infra/repositories.py | Flat (needs infra/database/ subdirectory + unit_of_work) |
| **Infrastructure (Messaging)** | — | Missing entirely |
| **Infrastructure (Workers)** | infra/workers/registry.py | Missing dispatcher, inbox consumer, inbox processor |
| **Presentation** | routes.py, schemas.py, 4 controllers | Partially canonical (missing mappers.py; controllers import from service/) |

## Imports Summary

- **Cross-module imports:** NONE
- **Shared imports:** `shared.domain.events.OutboxEventWriter`, `shared.infra.database.postgres_unit_of_work.PostgresUnitOfWork`, `shared.infra.database.base.BaseModel`, `shared.infra.database.inbox.InboxEventModel`, `shared.infra.database.outbox.OutboxEventModel`, `shared.infra.config.interface.unit_of_work.UnitOfWork`, `shared.infra.repositories.base_repository.BaseSQLAlchemyRepository`, `shared.domain.errors.NotFoundError`, `shared.presentation.interface.controller.Controller`, `shared.presentation.http.adapter`, `shared.presentation.http.request`, `shared.presentation.http.response`, `shared.application.transactional_handler.TransactionalHandler`, `shared.workers.contracts`

## Database

- **Schema:** `billing`
- **Tables:** plans, customers, subscriptions, payment_events, outbox_events, inbox_events
- **Entities:** Plan, Customer, Subscription, PaymentEvent
- **Cross-module FKs:** 2 (both to `identity.organizations.id`)
  - `billing.customers.organization_id -> identity.organizations.id`
  - `billing.subscriptions.organization_id -> identity.organizations.id`
- **Intra-module FKs:** `billing.subscriptions.customer_id -> billing.customers.id`, `billing.subscriptions.plan_id -> billing.plans.id`
- **Legacy schema refs (ai/knowledge/runtime):** NONE

## Routes

| Method | Path | Controller | Use Case |
|--------|------|-----------|----------|
| POST | /billing/plans | CreatePlanController | CreatePlanUseCase |
| GET | /billing/plans | ListPlansController | ListActivePlansUseCase |
| POST | /billing/subscriptions | CreateSubscriptionController | CreateSubscriptionUseCase |
| GET | /billing/organizations/{org_id}/subscription | GetOrganizationSubscriptionController | GetOrganizationSubscriptionUseCase |

## Events (Unversioned)

| Event Type | Aggregate | Emitted By |
|-----------|-----------|-----------|
| plan.created | Plan | CreatePlanUseCase |
| customer.created | Customer | CreateCustomerUseCase |
| subscription.created | Subscription | CreateSubscriptionUseCase |
| payment_event.* | PaymentEvent | HandlePaymentEventUseCase |

## Workers

- **Worker files:** 1 (`infra/workers/registry.py`)
- **Concrete workers:** 0 (registry is empty)
- **Existing workers needed:** BillingOutboxDispatcherWorker, BillingInboxConsumerWorker, BillingInboxProcessorWorker

## Tests

- **Existing billing tests:** 0
- **Existing architecture tests:** 35 pre-existing failures

## Risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| 2 cross-module FKs to identity.organizations | high | Defer to spec 099 (expand-migrate-contract) |
| 4 composers use PostgresUnitOfWork | high | Defer to spec 056 (BillingUnitOfWork) |
| Events are unversioned | medium | Defer to spec 090 (envelope standardization) |
| 0 existing billing tests | medium | Add in spec 058 (test phase) |
| Missing messaging/workers infrastructure | high | Create in spec 057 (messaging phase) |
