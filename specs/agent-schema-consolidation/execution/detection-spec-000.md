# Detection Results — Spec 000

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Baseline SHA `537e401` is ancestor of HEAD | PASS | 0 |
| Working tree clean | PASS | - |
| HEAD SHA | `cd4da371f07f1fb71c1c188e1368f5cd21dbd9ed` | - |

## Detection command 1: schema references

Command: `Select-String -Pattern "schema=['\"](ai|knowledge|runtime)['\"]|(ai|knowledge|runtime)\." src migrations tests`

Exit code: 0

Summary of findings:
- `src/modules/agent/infra/database/models.py` — ForeignKeys reference `ai.*`, `knowledge.*`, `runtime.*`
- `src/modules/metering/infra/database/models.py` — ForeignKeys reference `ai.*`
- `src/modules/observability/infra/database/models.py` — ForeignKeys reference `ai.*`, `runtime.*`
- `src/modules/tools/infra/database/models.py` — ForeignKeys reference `ai.*`
- `migrations/versions/0002_create_all_tables.py` — tables created in `ai`, `knowledge`, `runtime` schemas
- `migrations/versions/*.py` — operations on legacy schemas
- `src/modules/agent/infra/database/repositories.py` — raw SQL references `knowledge.document_chunks`
- `src/modules/agent/application/use_cases/*.py` — event_type strings with `runtime.`, `knowledge.` prefixes
- `tests/architecture/*.py` — legacy module references in test assertions

## Detection command 2: ForeignKey references

Command: `Select-String -Pattern "ForeignKey\(|create_foreign_key|ForeignKeyConstraint" src migrations`

Exit code: 0

Summary of findings:
- Intra-agent legacy FKs: `agent -> ai.*`, `agent -> knowledge.*`, `agent -> runtime.*`
- Cross-module FKs: `agent -> core.projects`, `agent -> identity.users`
- External FKs: `metering -> ai.agents`, `observability -> ai.agents`, `observability -> runtime.sessions`, `tools -> ai.agents`
- Historical migrations create cross-module FKs extensively

## Detection command 3: alembic current

Command: `alembic current`

Exit code: 1

Result: FAILED — no PostgreSQL database available (ConnectionDoesNotExistError). This is a known pendency.

## Detection command 4: alembic heads

Command: `alembic heads`

Exit code: 0

Result: `0014 (head)` — migration head is at revision 0014.

## Pendencies

- `alembic current` cannot execute without a running PostgreSQL instance. All `alembic` commands that require database connection will similarly fail.
- `rg` (ripgrep) is not available on this Windows environment; replaced with PowerShell `Select-String`.
