# Identity Module — Current-to-Canonical Migration Map

## Metadata

- **Module:** identity
- **Execution SHA:** `43da71a` (HEAD)
- **Date:** 2026-06-14
- **Total source files:** 47
- **Detection tool:** `Get-ChildItem` (substitute for `find`), `Select-String` (substitute for `rg`)

## Current Structure

```
src/modules/identity/
├── __init__.py                    # Exports routes, registry
├── application/
│   ├── __init__.py                # Empty
│   └── composers/                 # 13 composers (add_member, create_invite, create_organization, etc.)
├── domain/
│   ├── __init__.py                # Docstring only
│   ├── entities.py                # User, Organization, OrganizationMember, OrganizationInvite, UserSession
│   ├── enums.py                   # 6 StrEnum classes
│   ├── errors.py                  # 4 domain error classes
│   └── repositories.py            # 5 abstract repository interfaces
├── infra/
│   ├── __init__.py                # Docstring only
│   ├── models.py                  # 7 SQLAlchemy models (schema=identity)
│   ├── mappers.py                 # 10 mapper functions
│   ├── repositories.py            # 5 SQLAlchemy repository impls + OutboxEventWriter
│   └── workers/
│       ├── __init__.py            # Docstring only
│       └── registry.py            # IdentityWorkerRegistry
├── presentation/
│   ├── __init__.py                # Docstring only
│   ├── schemas.py                 # 11 Pydantic request/response models
│   ├── routes.py                  # 13 routes on APIRouter(prefix="/identity")
│   └── controllers/               # 13 controllers
├── service/
│   ├── __init__.py                # Docstring only
│   ├── dtos.py                    # 26 DTO classes (13 input + 13 output)
│   └── use_cases.py               # 14 use case classes
```

## Canonical Target Structure

```text
src/modules/identity/
├── application/
│   ├── composers/                 # Already exists (13 files) — keep
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
│   │   └── unit_of_work.py        # CREATE (future IdentityUnitOfWork)
│   ├── messaging/
│   │   ├── consumers.py           # CREATE (future RabbitMQ consumer)
│   │   ├── event_mappers.py       # CREATE (future event mapping)
│   │   └── publishers.py          # CREATE (future event publishing)
│   └── workers/
│       ├── inbox_consumer.py      # CREATE (future inbox consumer worker)
│       ├── inbox_processor.py     # CREATE (future inbox processor worker)
│       ├── outbox_dispatcher.py   # CREATE (future outbox dispatcher worker)
│       └── registry.py            # Already exists — keep
└── presentation/
    ├── controllers/               # Already exists — keep
    ├── mappers.py                 # CREATE (presentation-layer mappers, if needed)
    ├── routes.py                  # Already exists — keep
    └── schemas.py                 # Already exists — keep
```

## Per-File Classification

| # | Current Path | Action | Canonical Path | Layer |
|---|---|---|---|---|
| 1 | `__init__.py` | keep | `__init__.py` | module root |
| 2 | `application/__init__.py` | keep | `application/__init__.py` | application |
| 3 | `application/composers/__init__.py` | keep | `application/composers/__init__.py` | application |
| 4 | `application/composers/add_member_composer.py` | update | `application/composers/add_member_composer.py` | application |
| 5 | `application/composers/create_invite_composer.py` | update | `application/composers/create_invite_composer.py` | application |
| 6 | `application/composers/create_organization_composer.py` | update | `application/composers/create_organization_composer.py` | application |
| 7 | `application/composers/create_user_composer.py` | update | `application/composers/create_user_composer.py` | application |
| 8 | `application/composers/get_current_user_composer.py` | update | `application/composers/get_current_user_composer.py` | application |
| 9 | `application/composers/get_organization_composer.py` | update | `application/composers/get_organization_composer.py` | application |
| 10 | `application/composers/get_user_composer.py` | update | `application/composers/get_user_composer.py` | application |
| 11 | `application/composers/list_invites_composer.py` | update | `application/composers/list_invites_composer.py` | application |
| 12 | `application/composers/list_members_composer.py` | update | `application/composers/list_members_composer.py` | application |
| 13 | `application/composers/list_organizations_composer.py` | update | `application/composers/list_organizations_composer.py` | application |
| 14 | `application/composers/login_composer.py` | update | `application/composers/login_composer.py` | application |
| 15 | `application/composers/register_composer.py` | update | `application/composers/register_composer.py` | application |
| 16 | `application/composers/update_organization_composer.py` | update | `application/composers/update_organization_composer.py` | application |
| 17 | `domain/__init__.py` | keep | `domain/__init__.py` | domain |
| 18 | `domain/entities.py` | keep | `domain/entities.py` | domain |
| 19 | `domain/enums.py` | keep | `domain/enums.py` | domain |
| 20 | `domain/errors.py` | keep | `domain/errors.py` | domain |
| 21 | `domain/repositories.py` | keep | `domain/repositories.py` | domain |
| 22 | `infra/__init__.py` | keep | `infra/__init__.py` | infra |
| 23 | `infra/mappers.py` | move | `infra/database/mappers.py` | infra/database |
| 24 | `infra/models.py` | move | `infra/database/models.py` | infra/database |
| 25 | `infra/repositories.py` | move | `infra/database/repositories.py` | infra/database |
| 26 | `infra/workers/__init__.py` | keep | `infra/workers/__init__.py` | infra/workers |
| 27 | `infra/workers/registry.py` | keep | `infra/workers/registry.py` | infra/workers |
| 28 | `presentation/__init__.py` | keep | `presentation/__init__.py` | presentation |
| 29 | `presentation/controllers/__init__.py` | keep | `presentation/controllers/__init__.py` | presentation |
| 30 | `presentation/controllers/add_member_controller.py` | update | `presentation/controllers/add_member_controller.py` | presentation |
| 31 | `presentation/controllers/create_invite_controller.py` | update | `presentation/controllers/create_invite_controller.py` | presentation |
| 32 | `presentation/controllers/create_organization_controller.py` | update | `presentation/controllers/create_organization_controller.py` | presentation |
| 33 | `presentation/controllers/create_user_controller.py` | update | `presentation/controllers/create_user_controller.py` | presentation |
| 34 | `presentation/controllers/get_current_user_controller.py` | update | `presentation/controllers/get_current_user_controller.py` | presentation |
| 35 | `presentation/controllers/get_organization_controller.py` | update | `presentation/controllers/get_organization_controller.py` | presentation |
| 36 | `presentation/controllers/get_user_controller.py` | update | `presentation/controllers/get_user_controller.py` | presentation |
| 37 | `presentation/controllers/list_invites_controller.py` | update | `presentation/controllers/list_invites_controller.py` | presentation |
| 38 | `presentation/controllers/list_members_controller.py` | update | `presentation/controllers/list_members_controller.py` | presentation |
| 39 | `presentation/controllers/list_organizations_controller.py` | update | `presentation/controllers/list_organizations_controller.py` | presentation |
| 40 | `presentation/controllers/login_controller.py` | update | `presentation/controllers/login_controller.py` | presentation |
| 41 | `presentation/controllers/register_controller.py` | update | `presentation/controllers/register_controller.py` | presentation |
| 42 | `presentation/controllers/update_organization_controller.py` | update | `presentation/controllers/update_organization_controller.py` | presentation |
| 43 | `presentation/routes.py` | keep | `presentation/routes.py` | presentation |
| 44 | `presentation/schemas.py` | keep | `presentation/schemas.py` | presentation |
| 45 | `service/__init__.py` | shim | `service/__init__.py` | service (legacy) |
| 46 | `service/dtos.py` | move → shim | `application/dtos/` | application |
| 47 | `service/use_cases.py` | move → shim | `application/use_cases/` | application |

## Entities and Tables

- **Entities:** User, Organization, OrganizationMember, OrganizationInvite, UserSession
- **Tables:** identity.users, identity.organizations, identity.organization_members, identity.organization_invites, identity.user_sessions
- **Cross-module FKs:** None confirmed. All FKs reference identity.* tables only.
- **Schema:** `identity` (PostgreSQL schema)

## Routes (preserve)

| Method | Path | Composer | Controller |
|---|---|---|---|
| GET | /identity/organizations | list_organizations_composer | ListOrganizationsController |
| GET | /identity/users/me | get_current_user_composer | GetCurrentUserController |
| POST | /identity/auth/login | login_composer | LoginController |
| POST | /identity/auth/register | register_composer | RegisterController |
| POST | /identity/users | create_user_composer | CreateUserController |
| POST | /identity/organizations | create_organization_composer | CreateOrganizationController |
| POST | /identity/organizations/{org_id}/members | add_member_composer | AddMemberController |
| GET | /identity/organizations/{org_id} | get_organization_composer | GetOrganizationController |
| PATCH | /identity/organizations/{org_id} | update_organization_composer | UpdateOrganizationController |
| GET | /identity/organizations/{org_id}/members | list_members_composer | ListMembersController |
| POST | /identity/organizations/{org_id}/invites | create_invite_composer | CreateInviteController |
| GET | /identity/organizations/{org_id}/invites | list_invites_composer | ListInvitesController |
| GET | /identity/users/{user_id} | get_user_composer | GetUserController |

## Events

| Event Type | Producer | Status |
|---|---|---|
| user.created | CreateUserUseCase, RegisterUseCase | Unversioned |
| organization.created | CreateOrganizationUseCase, RegisterUseCase | Unversioned |
| organization.updated | UpdateOrganizationUseCase | Unversioned |
| organization.member_added | AddMemberToOrganizationUseCase, RegisterUseCase | Unversioned |
| organization.invite_created | InviteUserUseCase | Unversioned |

## Workers

| Worker | Location | Status |
|---|---|---|
| IdentityWorkerRegistry | infra/workers/registry.py | Empty (no workers registered) |

## UoW

All 13 composers use `PostgresUnitOfWork` (generic). No identity-specific UoW exists yet (planned for spec 036).

## Import Analysis

- **service/use_cases.py** depends on: domain entities/enums/errors/repositories, service/dtos, shared.domain.errors, shared.domain.events (OutboxEventWriter), shared.infra.crypto
- **Domain** imports: Python stdlib, uuid6, domain.enums, shared.domain.errors, shared.domain.objects (CursorPage)
- **Infra** imports: domain entities/enums/repositories, SQLAlchemy, shared.infra.database.base, shared.domain.events/objects, shared.infra.repositories.base_repository
- **Presentation** imports: service/dtos, service/use_cases, shared.presentation interface classes
- **Composers** import: service/use_cases, PostgresUnitOfWork, shared.presentation TransactionalHandler

## Migration Risks

| Risk | Severity | Mitigation |
|---|---|---|
| 13 composers import from `service/` | high | Spec 033 creates shims before removing service imports |
| 13 controllers import from `service/` | high | Spec 033 updates controller imports |
| PostgresUnitOfWork in all composers | high | Deferred to spec 036 |
| No existing unit tests for identity | medium | Specs 032-034 create first tests |
| `GetCurrentUserUseCase` is a stub | low | Not modified by this migration |
| `invited_by_user_id` hardcoded | low | Not modified by this migration |
