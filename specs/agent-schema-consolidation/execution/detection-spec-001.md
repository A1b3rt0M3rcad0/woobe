# Detection Results — Spec 001

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Baseline SHA `537e401` is ancestor of HEAD | PASS | 0 |
| Working tree clean | PASS | - |
| HEAD SHA | `26b74b4f2257dbd530bd2717965247fa0299b82e` | - |

## Detection command 1: schema references

Command: `Select-String -Pattern '__table_args__.*schema' src/modules/**/models.py`

Exit code: 0

Found: All agent-domain tables are in `ai`, `knowledge`, `runtime` schemas. Only `agent_outbox_events` and `agent_inbox_events` are in `agent`.

## Detection command 2: table/schema mapping

Command: `Select-String -Pattern '__tablename__|__table_args__.*schema' src/modules/**/models.py`

Exit code: 0

Result: Complete table-schema mapping extracted and documented in inventory files.

## Detection command 3: migration files

Command: `Get-ChildItem migrations/versions/*.py`

Exit code: 0

Result: 14 revision files (0001-0014). Head: 0014.

## Detection command 4: alembic heads

Command: `alembic heads`

Exit code: 0

Result: `0014 (head)`

## Detection command 5: alembic current

Command: `alembic current`

Exit code: 1

Result: FAILED — no PostgreSQL database available.

## Detection command 6: FK references

Command: `Select-String -Pattern 'ForeignKey\(' src/modules migrations`

Exit code: 0

Result: Complete FK inventory extracted and documented in `foreign-keys.md` (reused from spec 000).

## Pendências

- `alembic current` não disponível: sem PostgreSQL.
- Consultas a `pg_namespace`, `pg_class`, `pg_constraint`, `pg_indexes`, `pg_trigger`, `pg_proc`, `pg_policies` e `information_schema` não executadas: sem PostgreSQL.
- Row counts, checksums e drift `Base.metadata` vs catálogo real: não disponíveis.
