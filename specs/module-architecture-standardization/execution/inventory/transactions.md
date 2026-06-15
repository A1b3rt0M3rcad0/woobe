# Transaction and Unit of Work Inventory

**Date:** 2026-06-14
**Branch:** project-rai-playground_module-architecture-standardization
**SHA:** 369546b8ff3c87c9c1a4ce940f91ea4aebcacece

## Notes
- Generated during spec 015 execution.
- `rg` unavailable on Windows; substituted with `Select-String -Pattern 'UnitOfWork|TransactionalHandler|commit\(|rollback\('`.
- Detection scope: `src/modules` and `src/shared`.

## UoW Classes Found

### Abstract Contract
| Class | File | Layer | Owner |
|---|---|---|---|
| `UnitOfWork` (ABC) | `src/shared/infra/config/interface/unit_of_work.py` | shared/infra/config/interface | shared |

Defines: `session`, `commit()`, `rollback()`, `__aenter__`, `__aexit__`.

### Concrete Implementations
| Class | File | Layer | Owner |
|---|---|---|---|
| `PostgresUnitOfWork` | `src/shared/infra/database/postgres_unit_of_work.py` | shared/infra/database | shared |
| `AgentUnitOfWork` | `src/modules/agent/infra/database/unit_of_work.py` | agent/infra/database | agent |

`PostgresUnitOfWork` is a generic implementation with no repository awareness — just session commit/rollback.
`AgentUnitOfWork` is the only module-specific UoW. It coordinates **10 repositories** + Inbox + Outbox.

## TransactionalHandler Pattern

| Class | File | Role |
|---|---|---|
| `TransactionalHandler` | `src/shared/application/transactional_handler.py` | Wraps handler in `async with uow:` for auto-commit/rollback |

Used by every composer across all 7 modules. The handler receives a `PostgresUnitOfWork` (or `AgentUnitOfWork`) and the controller's `handle` method.

## PostgresUnitOfWork Usage by Module

### agent (44 files — 43 composers + 1 worker)
All composers use `PostgresUnitOfWork` even though `AgentUnitOfWork` exists in the same module.
Files: `src/modules/agent/application/composers/*.py` (43 files) + `src/modules/agent/infra/workers/ask_job_worker.py`

### billing (4 composers)
- `create_plan_composer.py`
- `create_subscription_composer.py`
- `get_organization_subscription_composer.py`
- `list_plans_composer.py`

### core (6 composers)
- `create_api_key_composer.py`
- `create_project_composer.py`
- `get_project_composer.py`
- `list_api_keys_composer.py`
- `list_projects_composer.py`
- `update_project_composer.py`

### identity (13 composers)
- `add_member_composer.py`, `create_invite_composer.py`, `create_organization_composer.py`, `create_user_composer.py`, `get_current_user_composer.py`, `get_organization_composer.py`, `get_user_composer.py`, `list_invites_composer.py`, `list_members_composer.py`, `list_organizations_composer.py`, `login_composer.py`, `register_composer.py`, `update_organization_composer.py`

### metering (3 composers)
- `get_agent_daily_usage_composer.py`, `get_project_daily_usage_composer.py`, `record_usage_composer.py`

### observability (4 composers)
- `add_trace_event_composer.py`, `create_trace_composer.py`, `get_trace_composer.py`, `list_traces_composer.py`

### tools (15 composers)
- `create_secret_composer.py`, `create_tool_composer.py`, `delete_tool_composer.py`, `execute_tool_composer.py`, `list_secrets_composer.py`, `list_tools_by_agent_composer.py`, `list_tools_composer.py`, `test_tool_composer.py`, `update_tool_composer.py`, `update_tool_status_composer.py` (and 5 more)

## commit() Call Sites

| File | Line | Context | Owner |
|---|---|---|---|
| `agent/infra/database/unit_of_work.py` | 116 | `await self._session.commit()` | agent (AgentUnitOfWork) |
| `shared/infra/database/postgres_unit_of_work.py` | 23 | `await self._session.commit()` | shared (PostgresUnitOfWork) |
| `shared/infra/database/session_manager.py` | 26 | `await self.__session.commit()` | shared (SessionManager) |
| `agent/infra/workers/ask_job_worker.py` | 95 | `await uow.commit()` | agent worker (via PostgresUnitOfWork) |
| `agent/application/use_cases/ask_agent_stream_service.py` | 134, 282, 351, 380, 505, 963 | `await db_session.commit()` | agent use_case (direct session — anti-pattern) |

## rollback() Call Sites

| File | Line | Context | Owner |
|---|---|---|---|
| `agent/infra/database/unit_of_work.py` | 118, 123, 131 | `await self._session.rollback()` / `await self.rollback()` | agent (AgentUnitOfWork) |
| `shared/infra/database/postgres_unit_of_work.py` | 25, 30, 38 | `await self._session.rollback()` / `await self.rollback()` | shared (PostgresUnitOfWork) |
| `shared/infra/database/session_manager.py` | 20, 41 | `await self.__session.rollback()` / `await self.rollback()` | shared (SessionManager) |
| `agent/infra/workers/inbox_consumer.py` | 62 | `await session.rollback()` | agent worker (direct session) |

## Repository UoW Awareness

Every module's `infra/repositories.py` accepts `AsyncSession | UnitOfWork` and checks `isinstance(self._session_or_uow, UnitOfWork)` to extract the session. This applies to:

| Module | File | Repository count | Accepts UoW? |
|---|---|---|---|
| agent | `src/modules/agent/infra/database/repositories.py` | 16 repos | Yes |
| billing | `src/modules/billing/infra/repositories.py` | 5 repos | Yes |
| core | `src/modules/core/infra/repositories.py` | 3 repos | Yes |
| identity | `src/modules/identity/infra/repositories.py` | 7 repos | Yes |
| metering | `src/modules/metering/infra/repositories.py` | 5 repos | Yes |
| observability | `src/modules/observability/infra/repositories.py` | 4 repos | Yes |
| tools | `src/modules/tools/infra/repositories.py` | 4 repos | Yes |

Base repository at `shared/infra/repositories/base_repository.py` also accepts `AsyncSession | UnitOfWork`.

## Classification Summary

### Module-Specific UoW
| Module | Has Own UoW? | UoW File |
|---|---|---|
| agent | Yes | `src/modules/agent/infra/database/unit_of_work.py` |
| billing | No | uses PostgresUnitOfWork (shared) |
| core | No | uses PostgresUnitOfWork (shared) |
| identity | No | uses PostgresUnitOfWork (shared) |
| metering | No | uses PostgresUnitOfWork (shared) |
| observability | No | uses PostgresUnitOfWork (shared) |
| tools | No | uses PostgresUnitOfWork (shared) |

### Composers using Generic PostgresUnitOfWork
| Module | Count | Target (spec 025-036) |
|---|---|---|
| agent | 44 | Migrate to AgentUnitOfWork |
| billing | 4 | Create BillingUnitOfWork |
| core | 6 | Create CoreUnitOfWork |
| identity | 13 | Create IdentityUnitOfWork |
| metering | 3 | Create MeteringUnitOfWork |
| observability | 4 | Create ObservabilityUnitOfWork |
| tools | 15 | Create ToolsUnitOfWork |
| **Total** | **89** | |

## Gaps and Risks

| Gap/Risk | Command needed | Severity |
|---|---|---|
| Agent has both AgentUnitOfWork and PostgresUnitOfWork in composers — redundant | Composer refactor (spec 025-036) | high |
| 6 modules have no module-specific UoW | Create per-module UoW (spec 036, 046, 056, 066, 076, 086) | high |
| `ask_agent_stream_service.py` commits directly via `await db_session.commit()` — bypasses UoW | Refactor to use UoW (spec 026) | high |
| `inbox_consumer.py` calls `await session.rollback()` directly | Refactor to use UoW (spec 027) | medium |
| `SessionManager` has its own commit/rollback — redundant if all code migrates to UoW | Remove or deprecate (spec 085) | medium |
| All 89 composers hardcode PostgresUnitOfWork — tight coupling | Inject UoW via DI (spec 025-036) | medium |

## Structured Command Output

Command: `Select-String -Pattern 'UnitOfWork|TransactionalHandler|commit\(|rollback\(' src/modules src/shared -Filter *.py`

Result: 103 unique files matched. Full paths listed above by module section.

## Acceptance Criteria

- [x] `transactions.md` exists and is not empty
- [x] SHA of inventory registered: `369546b`
- [x] Gaps have explicit commands and risks
- [x] Per-module UoW classification present
- [x] commit/rollback call sites catalogued
- [x] Composer count and target migration specs referenced
