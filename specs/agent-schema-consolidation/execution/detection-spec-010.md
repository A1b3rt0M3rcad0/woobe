# Detection Results — Spec 010

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Baseline `537e401` is ancestor of HEAD | PASS | 0 |
| Working tree clean | PASS | 0 |
| HEAD SHA | `bb24f9df666db221ced5f093a2442af91fb4fcb7` | - |

## Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Select-String `ForeignKey("core.` in agent models | 0 | 0 references found (all removed) |
| Select-String `ForeignKey("identity.` in agent models | 0 | 0 references found (all removed) |
| Select-String `ForeignKey("(ai|knowledge|runtime).` in external modules | 0 | 5 references found in metering (2), observability (2), tools (1) — all to be removed |
| `alembic heads` | 0 | `0017 (head)` (pre-migration) |

## Cross-module Foreign Keys removed

### Agent → core (14 constraints)

| Table | Column | Constraint name |
|---|---|---|
| provider_credentials | project_id | provider_credentials_project_id_fkey |
| agents | project_id | agents_project_id_fkey |
| agent_prompts | project_id | agent_prompts_project_id_fkey |
| agent_contracts | project_id | agent_contracts_project_id_fkey |
| agent_model_configs | project_id | agent_model_configs_project_id_fkey |
| agent_releases | project_id | agent_releases_project_id_fkey |
| agent_release_tests | project_id | agent_release_tests_project_id_fkey |
| document_collections | project_id | document_collections_project_id_fkey |
| documents | project_id | documents_project_id_fkey |
| document_chunks | project_id | document_chunks_project_id_fkey |
| knowledge_versions | project_id | knowledge_versions_project_id_fkey |
| sessions | project_id | sessions_project_id_fkey |
| messages | project_id | messages_project_id_fkey |
| ask_jobs | project_id | ask_jobs_project_id_fkey |

### Agent → identity (3 constraints)

| Table | Column | Constraint name |
|---|---|---|
| agent_prompts | created_by | agent_prompts_created_by_fkey |
| agent_releases | created_by | agent_releases_created_by_fkey |
| agent_releases | promoted_by | agent_releases_promoted_by_fkey |

### External → legacy agent (5 constraints)

| Schema | Table | Column | Constraint name |
|---|---|---|---|
| metering | usage_events | agent_id | usage_events_agent_id_fkey |
| metering | usage_daily_agent | agent_id | usage_daily_agent_agent_id_fkey |
| observability | traces | agent_id | traces_agent_id_fkey |
| observability | traces | session_id | traces_session_id_fkey |
| tools | tools | agent_id | tools_agent_id_fkey |

## Changes applied

### Migration 0018

- `migrations/versions/0018_remove_cross_module_foreign_keys.py` — created
- Revises: `0017`
- Upgrade: 22× `op.drop_constraint(..., type_="foreignkey")`
- Downgrade: 22× `op.create_foreign_key(...)`

### Agent models (models.py)

- Removed `ForeignKey("core.projects.id")` from all 14 project_id columns
- Removed `ForeignKey("identity.users.id")` from created_by (agent_prompts) and created_by/promoted_by (agent_releases)
- All columns remain as opaque UUIDs

### Metering models

- Removed `ForeignKey("ai.agents.id")` from UsageEventModel.agent_id
- Removed `ForeignKey("ai.agents.id")` from UsageDailyAgentModel.agent_id

### Observability models

- Removed `ForeignKey("ai.agents.id")` from TraceModel.agent_id
- Removed `ForeignKey("runtime.sessions.id")` from TraceModel.session_id

### Tools models

- Removed `ForeignKey("ai.agents.id")` from ToolModel.agent_id

### Allowlist

- 4 entries with `removal_spec: "010"` removed from legacy_schema_allowlist.yaml

### Architecture tests

- `test_spec_004_schema_guards.py`: MODELS_WITH_FK narrowed to agent models.py only
- `test_spec_010_cross_module_fk.py`: created with 9 tests covering FK absence, allowlist, and migration 0018

## Pendências

- Migration 0018 não executada (sem PostgreSQL).
- FKs removidas em nível de modelo SQLAlchemy e migration; validação real depende de PostgreSQL.
