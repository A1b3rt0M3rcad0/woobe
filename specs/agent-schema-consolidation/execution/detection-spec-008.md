# Detection Results — Spec 008

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Baseline `537e401` is ancestor of HEAD | PASS | 0 |
| Working tree clean | PASS | - |
| HEAD SHA | `bdc6fbe4a2e8930de856d27e23161795f1460846` | - |

## Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| `Select-String schema="runtime"` | 0 | 5 references in models.py (all allowlisted) |
| `alembic heads` | 0 | `0016 (head)` (pre-migration) |

## Runtime business tables moved (3)

| Source | Target | View created | Notes |
|---|---|---|---|
| `runtime.sessions` | `agent.sessions` | `runtime.sessions` | Compat view |
| `runtime.messages` | `agent.messages` | `runtime.messages` | Compat view |
| `runtime.ask_jobs` | `agent.ask_jobs` | `runtime.ask_jobs` | Compat view |

## Tables NOT moved

| Table | Reason |
|---|---|
| `runtime.outbox_events` | Messaging — spec 011 |
| `runtime.inbox_events` | Messaging — spec 011 |

## Migration file

- `migrations/versions/0017_move_runtime_tables_to_agent.py` — created
- Revises: `0016`
- Upgrade: 3x `ALTER TABLE ... SET SCHEMA agent` + 3x compat views
- Downgrade: reverse SET SCHEMA + DROP VIEW

## Pendências

- Migration não executada (sem PostgreSQL).
- Compat views permitem que código com `schema="runtime"` funcione até spec 009.
