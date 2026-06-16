# Detection Results — Spec 002

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Working tree clean | PASS | - |
| HEAD SHA | `18b503e68800a847591c0781f328551a9ee265f3` | - |

## Analysis performed

- Source→target mapping for all 15 business tables from `ai`, `knowledge`, `runtime`
- 6 legacy messaging tables identified with name collisions (need rename before SET SCHEMA)
- 18 cross-module FKs from agent tables to `core.projects` and `identity.users` identified for removal
- 5 external FKs from other modules to legacy schemas identified for re-pointing
- No index/constraint name collisions found
- `alembic heads` = `0014 (head)` (reused from spec 001)

## Pendências

- Verificação de colisões de sequences, views, funções, triggers no banco real pendente (sem PostgreSQL).
- Confirmação de que nenhum raw SQL usa schemas legados com three-part names pendente.
