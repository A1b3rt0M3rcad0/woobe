# Tests, Bootstrap, and Config Inventory

**Date:** 2026-06-14
**Branch:** project-rai-playground_module-architecture-standardization
**SHA:** 54ab80e

## Notes
- Generated during spec 018 execution.
- `find` and `sed` (Unix) unavailable on Windows; substituted with `Get-ChildItem -Recurse` and `Get-Content`.

## Test Suite Overview

| Metric | Value |
|---|---|
| Total test files | 150 (`.py` files under `tests/`) |
| Test directories | `architecture`, `contract`, `e2e`, `integration`, `messaging`, `modules`, `unit` |
| Conftest | `tests/conftest.py` (fixtures: anyio_backend, app, async_client, settings) |
| Test framework | pytest 8+ with pytest-asyncio, pytest-mock, httpx, aiosqlite, pytest-cov |

### Tests by Directory

| Directory | File Count | Purpose |
|---|---|---|
| `architecture/` | 62 | Module boundaries, layer deps, UoW, FKs, directory structure, worker locations, allowlists |
| `contract/` | 1 | HTTP route compatibility |
| `e2e/` | 0 (empty) | End-to-end tests |
| `integration/` | 2 | UoW transactions, Outbox/Inbox flow |
| `messaging/` | 9 | Event envelope, outbox/inbox pattern, RabbitMQ topology, idempotency, retry |
| `modules/agent/` | 20 | Agent-specific: unit tests, UoW, inbox/outbox, workers, rabbitmq, events |
| `unit/test_billing/` | 5 | Billing entities, dtos, enums, errors, use_cases |
| `unit/test_core/` | 5 | Core entities, dtos, enums, errors, use_cases |
| `unit/test_identity/` | 5 | Identity entities, dtos, enums, errors, use_cases |
| `unit/test_metering/` | 5 | Metering entities, dtos, enums, errors, use_cases |
| `unit/test_observability/` | 5 | Observability entities, dtos, enums, errors, use_cases |
| `unit/test_shared/` | 4 | Shared: crypto, errors, llm_usage, objects |
| `unit/test_tools/` | 5 | Tools entities, dtos, enums, errors, use_cases |

### Architecture Tests Detail

The `tests/architecture/` directory contains tests for:
- ADR presence (`test_adr_presence.py`)
- Layer dependencies (`test_layer_dependencies.py`)
- Module structure (`test_module_structure.py`)
- Module boundaries (`test_module_boundaries.py`, `test_shared_boundaries.py`, `test_agent_boundaries.py`)
- Public module entrypoints (`test_public_module_entrypoints.py`)
- Application boundaries (`test_application_boundaries.py`)
- UoW ownership (`test_uow_ownership.py`)
- No cross-module FKs (`test_no_cross_module_foreign_keys.py`)
- Runtime manifest consistency (`test_runtime_manifest_consistency.py`)
- Inventory artifacts (`test_inventory_artifacts.py`)
- Worker locations (`test_worker_locations.py`)
- Database boundaries (`test_database_boundaries.py`)
- API routes (`test_update_api_routes_to_agent.py`)
- Application bootstrap (`test_update_application_bootstrap.py`)
- Dependency injection (`test_update_dependency_injection_bindings.py`)
- Final validation (`test_final_architecture_validation.py`)

### Legacy Spec Tests (pre-existing, from old spec suite)
These tests reference the old `specs/` root and are expected to fail during migration:
- `test_architecture_decision_record_agent_bounded_context.py`
- `test_architecture_rules_modular_monolith_boundaries.py`
- `test_agent_target_directory_structure.py`
- `test_specs_inventory_outputs.py`
- `test_final_migration_report.py`
- `test_add_agent_boundary_architecture_tests.py`
- `test_add_shared_layer_architecture_tests.py`
- `test_add_worker_location_architecture_tests.py`
- `test_add_legacy_module_allowlist.py`
- `test_add_architecture_tests_for_module_boundaries.py`

## Bootstrap (src/main.py)

| Component | Details |
|---|---|
| Framework | FastAPI |
| App factory | `create_app()` function |
| Version | `0.1.0` |
| Router imports | All 7 modules: `identity`, `core`, `agent` (4 routers: main, ai, knowledge, runtime), `tools`, `metering`, `billing`, `observability` |
| Error handlers | DomainError, NotFoundError, ConflictError, ValidationError, PydanticValidationError, RequestValidationError, Exception |
| Middleware | CORS middleware + custom cors_safe_guard |
| Startup | Creates engine, tests connection |
| Shutdown | Disposes engine |
| Health | `GET /health` -> `{"status": "ok"}` |
| Session | `shared.infra.database.session.create_session_factory` |

## Alembic Config (migrations/)

| Component | Details |
|---|---|
| Location | `migrations/` (from `alembic.ini`) |
| Env | `migrations/env.py` — async, loads all 7 modules' models |
| Target metadata | `Base.metadata` (from `shared.infra.database.base`) |
| Schema imports | Wildcard imports from all 7 modules' `infra/models.py` |
| URL config | Overrides `sqlalchemy.url` from `PROJECTRAI_DATABASE_URL` env |
| Sync URL | `+asyncpg` replaced with `+psycopg2` for offline |
| Async URL | `+psycopg2` replaced with `+asyncpg` for online |
| Total migrations | 14 versions (0001 through 0014) + `env.py` + `script.py.mako` |

### Migration Versions
| Version | Description |
|---|---|
| 0001 | Create schemas |
| 0002 | Create all tables |
| 0003 | Add metadata to provider credentials |
| 0004 | Add mode to sessions |
| 0005 | Fix datetime timezones |
| 0006 | Add ask jobs table |
| 0007 | Create agent versioning tables |
| 0008 | Add release snapshot fields |
| 0009 | Add agent release missing fields |
| 0010 | Add production unique constraint |
| 0011 | Add fallback fields to agent releases |
| 0012 | Make tool agent_id nullable |
| 0013 | Create agent outbox events |
| 0014 | Create agent inbox events |

## Config (pyproject.toml)

| Section | Details |
|---|---|
| Python | >=3.14 |
| Dependencies | alembic, asyncpg, cryptography, fastapi, langchain, langchain-core, langchain-openai, pgvector, psycopg2-binary, pydantic, pydantic-settings, sqlalchemy, uuid6, aio-pika, uvicorn |
| Test deps | pytest>=8.0, pytest-asyncio>=0.25, pytest-mock>=3.14, httpx>=0.28, aiosqlite>=0.21, pytest-cov>=6.0 |
| Dev deps | pyright>=1.1.410, ruff>=0.15.15 |

## Gaps and Risks

| Gap/Risk | Command needed | Severity |
|---|---|---|
| e2e tests directory exists but has no test files | Create e2e tests (spec 105) | low |
| `tests/unit/test_core/` has no `__init__.py` (others do) | Add `__init__.py` | low |
| Architecture tests have 34 pre-existing failures (old spec suite references) | Fix or remove legacy tests (spec 107) | medium |
| Async Alembic env mixed sync/async URL conversion (fragile) | Standardize expand-migrate-contract (spec 098) | medium |
| Wildcard model imports in migrations/env.py (`from X.models import *`) | Replace with explicit imports (spec 098) | medium |
| `sys.path.insert(0, ...)` in both `conftest.py` and `migrations/env.py` | Standardize bootstrap (spec 097) | low |
| Test fixtures create a new `create_app()` per test — no DB isolation | Add integration DB fixtures (spec 038-088) | medium |
| No Ruff, Pyright, or pytest config in `pyproject.toml` | Add tool config (spec 097) | low |

## Acceptance Criteria

- [x] `tests-bootstrap.md` exists and is not empty
- [x] SHA of inventory registered: `54ab80e`
- [x] Gaps have explicit commands and risks
- [x] Test suite structure classified
- [x] Bootstrap (main.py) documented
- [x] Alembic/migration config documented
- [x] pyproject.toml dependencies and config documented
