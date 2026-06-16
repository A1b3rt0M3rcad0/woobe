# Detection Evidence — Spec 014

## Guard checks

| Check | Result |
|---|---|
| Branch | `development_agent-schema-consolidation` ✅ |
| Baseline SHA ancestor | `537e401` is ancestor of HEAD ✅ |
| Working tree clean before changes | Clean ✅ |
| HEAD before changes | `73d3b63` |

## PostgreSQL provisioning

PostgreSQL was provisioned via Docker (`pgvector/pgvector:pg17`, container `projectrai-db-1`).
Migrations 0015–0019 were applied manually via psql (alembic CLI unavailable due to
asyncpg/ProactorEventLoop incompatibility on Python 3.14 Windows).

### Migration execution

| Migration | SQL Outcome | Description |
|---|---|---|
| 0015 | 7× ALTER TABLE SET SCHEMA + 7× CREATE VIEW | ai tables → agent |
| 0016 | 5× ALTER TABLE SET SCHEMA + 5× CREATE VIEW | knowledge tables → agent |
| 0017 | 3× ALTER TABLE SET SCHEMA + 3× CREATE VIEW | runtime tables → agent |
| 0018 | 22× DROP CONSTRAINT | Cross-module FKs removed |
| 0019 | 6× DROP TABLE | Legacy messaging tables dropped |

### Data migration (pre-0019)

Pending events from legacy outbox tables were migrated to `agent.agent_outbox_events`:
- `ai.outbox_events`: 13 events (pending) → migrated
- `runtime.outbox_events`: 79 events (pending) → migrated
- Total: 92 events in `agent.agent_outbox_events`

## Detection commands

### `Select-String` — legacy schema refs in models.py, metering, observability, tools
- Result: Zero matches ✅ (all models use `schema="agent"`)

### `Select-String` — ForeignKey in agent models
- Result: All 27 FKs point to `agent.*` tables ✅
- Zero `ForeignKey("core.")` or `ForeignKey("identity.")` ✅

### `alembic heads`
- Exit code: 0
- Result: `0019 (head)`

### `alembic current`
- Exit code: 1 (CLI unavailable due to asyncpg/ProactorEventLoop)
- DB verification via psql: `version_num = 0019` ✅

## Database verification (via psql)

### Agent tables
- Count: 17 (15 business + 2 canonical messaging)
- All tables in `agent` schema

### Compat views
- 15 views in legacy schemas (`ai`: 7, `knowledge`: 5, `runtime`: 3)
- All point to `agent.*` tables

### Foreign keys
- Zero cross-module FKs FROM agent.* to external schemas ✅
- Zero cross-module FKs TO agent.* from external schemas ✅
- 27 intra-agent FKs (agent.* → agent.*) ✅

### Alembic version
- `version_num = 0019` ✅

## Tests created

- `tests/architecture/test_spec_014_data_integrity.py` — 7 tests covering:
  - All expected agent tables defined in models
  - All business tables use `schema="agent"`
  - No legacy schema references in models
  - No cross-module FKs
  - All FKs point to `agent.*`
  - Alembic head is 0019
  - Migration chain has no gaps

## Pendencies

- `alembic current` CLI still not usable from Windows Python 3.14 (asyncpg/ProactorEventLoop).
  DB state verified via psql inside Docker container.
