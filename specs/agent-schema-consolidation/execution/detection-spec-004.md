# Detection Results — Spec 004

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Working tree clean | PASS | - |
| HEAD SHA | `eced77e4c3e56479f7b7e14701edad6832f34848` | - |

## Analysis performed

- Created `legacy_schema_allowlist.yaml` with known legacy schema references
- Created `test_spec_004_schema_guards.py` with 4 test classes:
  - `TestNoNewLegacySchemaReferences` — blocks new `schema="ai|knowledge|runtime"` in models.py
  - `TestLegacyForeignKeyReferences` — blocks new `ForeignKey("ai|knowledge|runtime.")` outside allowlist
  - `TestAgentTableSchemaClassification` — classifies all 19 agent tables by current/target schema
  - `TestMigrationLegacySchemaGuard` — blocks new migration operations in legacy schemas

## Pendências

- Testes de regressão do `tests/architecture` completo: 42 pre-existing failures (unchanged).
