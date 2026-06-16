# Detection Evidence — Spec 012

## Guard checks

| Check | Result |
|---|---|
| Branch | `development_agent-schema-consolidation` ✅ |
| Baseline SHA ancestor | `537e401` is ancestor of HEAD ✅ |
| Working tree clean before changes | Clean ✅ |
| HEAD before changes | `8b9f9e954dc25f99b1509243848ff23ecfe2e87b` |

## Detection commands

### `alembic heads`
- Exit code: 0
- Result: `0019 (head)`

### `alembic current`
- Exit code: 1
- Pendência: PostgreSQL não está disponível neste ambiente.

### `Select-String` — `schema="(ai|knowledge|runtime)"` in `src/`
- Result: Zero matches ✅

### `Select-String` — `modules.(ai|knowledge|runtime)` import patterns in `src/`
- Result: Zero matches ✅

### `Select-String` — `schema="(ai|knowledge|runtime)"` in `src/` yaml/config
- Result: Zero matches ✅

### `Select-String` — `(ai|knowledge|runtime)\.` in `src/modules/agent`
- Matches: Only `agent.knowledge.document_indexed.v1` in event types/routing keys — these are agent-bounded-context event naming conventions, not legacy schema references.

### `Select-String` — `modules.(ai|knowledge|runtime)` in `tests/`
- Result: Only architecture test files that deliberately test boundary enforcement. These are not production code.

### Allowlist state
- `legacy_schema_allowlist.yaml` has 3 entries, all with `removal_spec: "016"`, covering only historical migrations. ✅ No executable code allowlists remain.

## Conclusão

A spec 012 não requer alterações de código executável porque as specs 009–011 já removeram todas as referências a schemas legados em `schema=`, imports de módulos e configuração. Os únicos `modules.ai|knowledge|runtime` remanescentes estão em testes de arquitetura que validam o boundary enforcement deliberadamente.
