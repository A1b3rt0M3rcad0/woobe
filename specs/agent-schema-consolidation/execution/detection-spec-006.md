# Detection Results — Spec 006

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Baseline `537e401` is ancestor of HEAD | PASS | 0 |
| Working tree clean | PASS | - |
| HEAD SHA | `c7f8c0644fe9cc11d89eeac88bd5ee52e26709ed` | - |

## Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| `Select-String schema="ai"` | 0 | 9 references in models.py (all allowlisted) |
| `alembic heads` | 0 | `0014 (head)` (pre-migration) |

## AI business tables moved (7)

| Source | Target | View created | Notes |
|---|---|---|---|
| `ai.provider_credentials` | `agent.provider_credentials` | `ai.provider_credentials` | Compat view |
| `ai.agents` | `agent.agents` | `ai.agents` | Compat view |
| `ai.agent_prompts` | `agent.agent_prompts` | `ai.agent_prompts` | Compat view |
| `ai.agent_contracts` | `agent.agent_contracts` | `ai.agent_contracts` | Compat view |
| `ai.agent_model_configs` | `agent.agent_model_configs` | `ai.agent_model_configs` | Compat view |
| `ai.agent_releases` | `agent.agent_releases` | `ai.agent_releases` | Compat view |
| `ai.agent_release_tests` | `agent.agent_release_tests` | `ai.agent_release_tests` | Compat view |

## Tables NOT moved (excluded per spec)

| Table | Reason |
|---|---|
| `ai.outbox_events` | Messaging table — moved in spec 011 |
| `ai.inbox_events` | Messaging table — moved in spec 011 |

## Migration file

- `migrations/versions/0015_move_ai_tables_to_agent.py` — created
- Revises: `0014`
- Upgrade: 7x `ALTER TABLE ... SET SCHEMA agent` + 7x `CREATE OR REPLACE VIEW ai.<table> AS ...`
- Downgrade: DROP VIEW + reverse SET SCHEMA

## Pendências

- Migration não executada (sem PostgreSQL). Validação real depende de banco.
- Compat views permitem que código com `schema="ai"` funcione até spec 009.
