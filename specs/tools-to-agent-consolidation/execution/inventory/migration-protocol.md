# Migration Protocol — Tools to Agent

## Alembic baseline

- Current head: `0020`
- 20 migration versions (0001-0020)
- Previous schema migrations (0015-0020) moved ai/knowledge/runtime → agent using expand-migrate-contract

## Phases

### Phase 1: Expand (specs 004-010)

Add agent-side structures without dropping legacy tools structures.

| Step | Spec | Description |
|---|---|---|
| 1.1 | 004 | Add architecture guards and characterization tests for current behavior |
| 1.2 | 005 | Move tools domain contracts (entities, enums, errors, events, repositories) into agent module |
| 1.3 | 006 | Move tools DTOs and use cases into agent application layer |
| 1.4 | 007 | Consolidate tool execution and secure secret resolution |
| 1.5 | 008 | Integrate models, mappers, repositories into AgentUnitOfWork |
| 1.6 | 009 | Move controllers, composers, schemas, routes preserving API compatibility |

**Gate:** All tests pass. No legacy behavior broken.

### Phase 2: Migrate (specs 010-012)

Consolidate events, Outbox/Inbox, workers, and database.

| Step | Spec | Description |
|---|---|---|
| 2.1 | 010 | Consolidate events, Outbox, Inbox, workers, and registry |
| 2.2 | 011 | Migrate tools/secrets business tables to agent schema (SET SCHEMA or CREATE+COPY+DROP) |
| 2.3 | 012 | Consolidate tools legacy Outbox and Inbox |

**Gate:** Zero pending events in tools.outbox_events. All consumers switched to agent outbox/inbox.

### Phase 3: Cutover (specs 013-014)

Update imports, bootstrap, Alembic, and dependency injection. Run shim period with observability.

| Step | Spec | Description |
|---|---|---|
| 3.1 | 013 | Update imports, bootstrap, Alembic, and dependency injection |
| 3.2 | 014 | Execute cutover with temporary shims and observability |

**Gate:** No errors in shim period. Legacy routes returning correct responses.

### Phase 4: Contract (specs 015-017)

Remove legacy structures and validate final architecture.

| Step | Spec | Description |
|---|---|---|
| 4.1 | 015 | Add security, transaction, and concurrency test suite |
| 4.2 | 016 | Remove legacy tools module, shims, views, and tools schema |
| 4.3 | 017 | Final validation and consolidation report |

**Gate:** No remaining references to `modules.tools` in production code. No `tools` schema.

## Rollback protocol

| Phase | Rollback action |
|---|---|
| Expand | Revert code changes. Legacy module intact. No data loss. |
| Migrate (before contract) | Swap back to legacy schema/outbox via config toggle or revert migration |
| Contract | Cannot rollback after DROP SCHEMA. Restore from backup. |

## Compatibility rules

- All existing HTTP routes under `/tools`, `/agents/{agent_id}/tools`, `/secrets` must remain functional during all phases
- Event consumers must not lose messages during cutover
- Agents using tools at runtime must not experience interruption
- Secret encryption/decryption must remain consistent across migration

## Shims

| Shim | Removed in |
|---|---|
| `src/modules/agent/infra/adapters/tools_tool_executor.py` (importlib) | spec 013 |
| `src/modules/agent/infra/adapters/tools_tool_repository.py` (importlib) | spec 013 |
| Legacy /tools routes in tools.presentation | spec 016 |

Detection: Alembic head is `0020`, no pending migrations.
