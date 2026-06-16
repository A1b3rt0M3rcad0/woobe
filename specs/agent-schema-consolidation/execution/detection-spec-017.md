# Detection Evidence — Spec 017 (Final Validation)

## Guard checks

| Check | Result |
|---|---|
| Branch | `development_agent-schema-consolidation` ✅ |
| Baseline SHA ancestor | `537e401` is ancestor of HEAD ✅ |
| Working tree clean before changes | Clean ✅ |
| HEAD before changes | `6e9b1ed` |

## Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: branch check | 0 | `development_agent-schema-consolidation` |
| Guard: baseline SHA ancestor | 0 | `537e401` is ancestor of HEAD |
| Guard: working tree clean | 0 | Clean |
| `Select-String` legacy schema refs in src | 0 | Zero matches ✅ |
| `Select-String` legacy imports in src | 0 | Zero matches ✅ |
| `alembic heads` | 0 | `0020 (head)` |
| `alembic current` (via psql) | 0 | `version_num = 0020` ✅ |

## Database verification (via psql)

| Check | SQL | Result |
|---|---|---|
| Legacy schemas | `SELECT nspname FROM pg_namespace WHERE nspname IN ('ai','knowledge','runtime')` | Zero rows ✅ |
| Agent tables | `SELECT count(*) FROM information_schema.tables WHERE table_schema = 'agent'` | 17 ✅ |
| Cross-module FKs from agent | `SELECT * FROM pg_constraint WHERE contype='f' AND conrelid::regclass::text LIKE 'agent.%' AND confrelid::regclass::text NOT LIKE 'agent.%'` | Zero ✅ |
| Cross-module FKs to agent | `SELECT * FROM pg_constraint WHERE contype='f' AND confrelid::regclass::text LIKE 'agent.%' AND conrelid::regclass::text NOT LIKE 'agent.%'` | Zero ✅ |
| Alembic version | `SELECT version_num FROM alembic_version` | 0020 ✅ |

## Allowlist state

| Allowlist | Entries | Action |
|---|---|---|
| `legacy_schema_allowlist.yaml` | 3 (historical migrations, removal_spec:016) | Kept (justified historical exceptions) |
| `legacy_import_allowlist.yaml` | 0 | Empty (no action needed) |
| `legacy_database_fk_allowlist.yaml` | 27 (removal_spec:134, outside scope) | Unchanged (outside this scope) |

## Tests created

- `tests/architecture/test_spec_017_final_validation.py` — 12 tests covering:
  - No legacy schema references in source
  - No legacy module imports in source
  - Migration chain head 0020
  - Migration chain is linear
  - All agent tables defined in models.py
  - No cross-module FKs in agent models

## Acceptance criteria

1. Todas as validações obrigatórias passam ✅ (12 new tests pass)
2. Schemas legados e FKs cross-module são zero ✅ (verified via psql)
3. Relatório final contém evidências ✅ (final-report.md populated)
