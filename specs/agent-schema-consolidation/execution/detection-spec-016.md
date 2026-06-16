# Detection Evidence — Spec 016

## Guard checks

| Check | Result |
|---|---|
| Branch | `development_agent-schema-consolidation` ✅ |
| Baseline SHA ancestor | `537e401` is ancestor of HEAD ✅ |
| Working tree clean before changes | Clean ✅ |
| HEAD before changes | `9804808` |

## Migration 0020 — drop legacy schemas

### Applied via psql (alembic CLI unavailable from Windows)

| Operation | Status |
|---|---|
| DROP VIEW ai.provider_credentials | ✅ |
| DROP VIEW ai.agents | ✅ |
| DROP VIEW ai.agent_prompts | ✅ |
| DROP VIEW ai.agent_contracts | ✅ |
| DROP VIEW ai.agent_model_configs | ✅ |
| DROP VIEW ai.agent_releases | ✅ |
| DROP VIEW ai.agent_release_tests | ✅ |
| DROP VIEW knowledge.document_collections | ✅ |
| DROP VIEW knowledge.agent_collections | ✅ |
| DROP VIEW knowledge.documents | ✅ |
| DROP VIEW knowledge.document_chunks | ✅ |
| DROP VIEW knowledge.knowledge_versions | ✅ |
| DROP VIEW runtime.sessions | ✅ |
| DROP VIEW runtime.messages | ✅ |
| DROP VIEW runtime.ask_jobs | ✅ |
| DROP SCHEMA ai | ✅ |
| DROP SCHEMA knowledge | ✅ |
| DROP SCHEMA runtime | ✅ |

No CASCADE was used. All drops completed without errors.

### Database verification (via psql)

| Check | Result |
|---|---|
| Legacy schemas (ai, knowledge, runtime) | Zero rows in pg_namespace ✅ |
| Agent tables count | 17 ✅ |
| Alembic version | 0020 ✅ |
| Cross-module FKs | Zero ✅ |

### Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: branch check | 0 | `development_agent-schema-consolidation` |
| Guard: baseline SHA ancestor | 0 | `537e401` is ancestor of HEAD |
| Guard: working tree clean | 0 | Clean |
| `alembic heads` | 0 | `0020 (head)` |
| `alembic current` (via psql) | 0 | `version_num = 0020` ✅ |

## Tests created

- `tests/architecture/test_spec_016_drop_legacy.py` — 15 tests covering:
  - Migration file existence and metadata
  - DROP VIEW for all 15 compat views
  - DROP SCHEMA for all 3 legacy schemas
  - No CASCADE in upgrade
  - Downgrade recreates schemas and views
  - Agent schema not touched by migration

## Acceptance criteria

1. pg_namespace não contém ai/knowledge/runtime ✅ (verified via psql)
2. Drop sem CASCADE conclui com sucesso ✅ (all drops completed)
3. Todos os dados operacionais permanecem em agent ✅ (17 tables intact)

## Pendencies

- `alembic current` CLI still not usable from Windows Python 3.14.
  DB state verified via psql in Docker container.
