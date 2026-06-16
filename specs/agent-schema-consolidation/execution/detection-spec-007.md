# Detection Results — Spec 007

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Baseline `537e401` is ancestor of HEAD | PASS | 0 |
| Working tree clean | PASS | - |
| HEAD SHA | `2d0a0564e58909a2e96e97a87e0112a5bb130c35` | - |

## Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| `Select-String schema="knowledge"` | 0 | 7 references in models.py (all allowlisted) |
| `alembic heads` | 0 | `0015 (head)` (pre-migration) |

## Knowledge business tables moved (5)

| Source | Target | View created | Notes |
|---|---|---|---|
| `knowledge.document_collections` | `agent.document_collections` | `knowledge.document_collections` | Compat view |
| `knowledge.agent_collections` | `agent.agent_collections` | `knowledge.agent_collections` | Compat view |
| `knowledge.documents` | `agent.documents` | `knowledge.documents` | Compat view |
| `knowledge.document_chunks` | `agent.document_chunks` | `knowledge.document_chunks` | Compat view |
| `knowledge.knowledge_versions` | `agent.knowledge_versions` | `knowledge.knowledge_versions` | Compat view |

## Tables NOT moved

| Table | Reason |
|---|---|
| `knowledge.outbox_events` | Messaging — spec 011 |
| `knowledge.inbox_events` | Messaging — spec 011 |

## Migration file

- `migrations/versions/0016_move_knowledge_tables_to_agent.py` — created
- Revises: `0015`
- Upgrade: 5x `ALTER TABLE ... SET SCHEMA agent` + 5x compat views
- Downgrade: reverse SET SCHEMA + DROP VIEW

## Pendências

- Migration não executada (sem PostgreSQL).
- Compat views permitem que código com `schema="knowledge"` funcione até spec 009.
