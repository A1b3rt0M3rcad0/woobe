# Cutover report

## Summary

Tools-to-agent consolidation cutover verified. Agent is the unique source for all tool capabilities: domain contracts, DTOs, use cases, executors, secret resolution, repositories, models, Unit of Work, controllers, routes, event handlers, outbox/inbox, and workers.

## Component status

| Component | Legacy (tools) | Active (agent) | Cutover |
|---|---|---|---|
| Domain contracts | `modules.tools.domain.*` (shim) | `modules.agent.domain.*` | Completed (spec 005) |
| DTOs | `modules.tools.application.dtos` (shim) | `modules.agent.application.dtos` | Completed (spec 006) |
| Use cases | `modules.tools.application.use_cases` (shim) | `modules.agent.application.use_cases` | Completed (spec 006) |
| Ports (execution, cipher, resolver) | None (inline infra) | `modules.agent.application.ports` | Completed (spec 006) |
| HTTP executor | `ToolsToolExecutor` (importlib shim) | `modules.agent.infra.adapters.HttpToolExecutor` | Completed (spec 007) |
| Secret cipher | Inline in use case | `modules.agent.infra.adapters.SecretCipherAdapter` | Completed (spec 007) |
| Secret resolver | `get_by_name()` bug (no args) | `modules.agent.infra.adapters.ToolSecretResolverAdapter` | Completed (spec 007) |
| Models | `tools.ToolModel`, `tools.SecretModel` | `agent.AgentToolModel`, `agent.AgentToolSecretModel` | Completed (spec 008) |
| Repositories | `modules.tools.infra.database.repositories` | `modules.agent.infra.database.repositories` | Completed (spec 008) |
| Unit of Work | `ToolsUnitOfWork` (separate session) | `AgentUnitOfWork.tools` + `AgentUnitOfWork.tool_secrets` | Completed (spec 008) |
| Routes (HTTP) | `modules.tools.presentation.routes` (shim) | `modules.agent.presentation.routes.tools_router` | Completed (spec 009, 013) |
| Controllers | `modules.tools.presentation.controllers` (shim) | `modules.agent.presentation.controllers` | Completed (spec 009) |
| Event handlers | `ToolsInboxEventRouter` (empty stubs) | `agent.infra.messaging.inbox_handlers` (real handlers) | Completed (spec 010) |
| Worker registry | `register_tools_workers()` (no-op) | `register_agent_workers()` with tool handlers | Completed (spec 010) |
| Business tables | `tools.tools`, `tools.secrets` (compat views) | `agent.tools`, `agent.tool_secrets` | Completed (spec 011) |
| Messaging tables | `tools.outbox_events`, `tools.inbox_events` (compat views) | `agent.agent_outbox_events`, `agent.agent_inbox_events` | Completed (spec 012) |
| Alembic metadata | `modules.tools.infra.database.models` import | Removed; agent metadata only | Completed (spec 013) |
| Bootstrap import | `modules.tools.presentation.routes` | `modules.agent.presentation.routes.tools_router` | Completed (spec 013) |

## Legacy shims still present

The following legacy `modules.tools` files remain as shims. They are not imported by production code but exist so spec 016 can remove them in a single cleanup commit:

- `src/modules/tools/__init__.py`
- `src/modules/tools/domain/*.py`
- `src/modules/tools/application/*.py`
- `src/modules/tools/infra/database/*.py`
- `src/modules/tools/infra/messaging/*.py`
- `src/modules/tools/infra/workers/*.py`
- `src/modules/tools/presentation/*.py`
- `src/modules/agent/infra/adapters/tools_tool_executor.py` (dead code, zero references)
- `src/modules/agent/infra/adapters/tools_tool_repository.py` (dead code, zero references)

## Test results

| Test suite | Result |
|---|---|
| `pytest tests/contract -q` | 40 passed |
| `pytest tests/integration/agent -q` | 32 passed |
| `pytest tests/unit/agent -q` | 65 passed |
| `pytest tests/architecture/test_update_alembic_or_database_migrations.py` | 12 passed |
| `python -m compileall -q src` | 0 errors |

## Risks

- Database migrations 0021 and 0022 require a running PostgreSQL to execute; `alembic upgrade head` not executed in this session.
- No E2E tests exist yet (spec 015 adds security/transaction tests).
- Legacy `tools_tool_executor.py` and `tools_tool_repository.py` are dead code but not yet removed.

## Go/No-Go

Go. Agent is the unique source of truth for all tool capabilities. All production code paths use agent module. Legacy shims are inert and covered by compatibility views.
