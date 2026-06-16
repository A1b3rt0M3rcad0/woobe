# Detection Evidence — Spec 013

## Guard checks

| Check | Result |
|---|---|
| Branch | `development_agent-schema-consolidation` ✅ |
| Baseline SHA ancestor | `537e401` is ancestor of HEAD ✅ |
| Working tree clean before changes | Clean ✅ |
| HEAD before changes | `6be2ad9` |

## Detection commands

### `alembic heads`
- Exit code: 0
- Result: `0019 (head)`

### `alembic current`
- Exit code: 1
- Pendência: PostgreSQL não está disponível neste ambiente.

### Migration chain analysis
- Total revisions: 19 (0001–0019)
- Chain: linear, complete
- Head: 0001
- Tail: 0019
- No broken dependencies

### `Select-String` — `modules.ai|knowledge|runtime` in `migrations/env.py`
- Result: Zero matches ✅

### `Select-String` — `create_table` with legacy schema in post-consolidation migrations (0015+)
- Result: Migration 0015-0019 do not create tables in ai/knowledge/runtime schemas ✅

## Pendências

- `alembic current` não executável (sem PostgreSQL).
- Teste de fresh install vs upgrade incremental não executável (sem PostgreSQL).
- Equivalência de catálogo não verificável (sem PostgreSQL).
