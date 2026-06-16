# Detection Evidence — Spec 015

## Guard checks

| Check | Result |
|---|---|
| Branch | `development_agent-schema-consolidation` ✅ |
| Baseline SHA ancestor | `537e401` is ancestor of HEAD ✅ |
| Working tree clean before changes | Clean ✅ |
| HEAD before changes | `aaad642` |

## Cutover verification

### Schema references in `src/`
Command: `Select-String schema='ai|knowledge|runtime' in src/**/*.py`
Result: Zero matches ✅ — all models reference `schema="agent"`

### Legacy module imports in `src/`
Command: AST analysis of imports from `modules.ai`, `modules.knowledge`, `modules.runtime`
Result: Zero imports ✅ — all imports point to `modules.agent`

### Database state (via psql)
- All 17 agent tables in `agent` schema ✅
- 15 compat views in legacy schemas (ai:7, knowledge:5, runtime:3) — temporary
- Zero cross-module FKs in any direction ✅
- `alembic_version = 0019` ✅

### Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: branch check | 0 | `development_agent-schema-consolidation` |
| Guard: baseline SHA ancestor | 0 | `537e401` is ancestor of HEAD |
| Guard: working tree clean | 0 | Clean |
| `Select-String` legacy schema refs | 0 | Zero matches ✅ |
| `Select-String` legacy imports | 0 | Zero matches ✅ |
| `alembic heads` | 0 | `0019 (head)` |
| `alembic current` (via psql) | 0 | `version_num = 0019` ✅ |

## Tests created

- `tests/architecture/test_spec_015_cutover.py` — 8 tests covering:
  - No legacy schema references in source code
  - No legacy module imports in source code
  - Database has agent schema as canonical

## Cutover summary

The application cutover to `agent` schema is effectively complete:
- All migrations 0015-0019 have been applied to the database
- All SQLAlchemy models reference `schema="agent"`
- All intra-agent FKs point to `agent.*`
- No cross-module FKs remain
- No legacy schema references in application code
- Compat views continue to exist for external compat and rollback

## Observation window

Compatibility period for legacy schemas (ai, knowledge, runtime) is active.
Legacy schemas and compat views will be removed in spec 016 after confirming
no external dependencies remain.

## Pendencies

- `alembic current` CLI still not usable from Windows Python 3.14.
  DB state verified via psql in Docker container.
