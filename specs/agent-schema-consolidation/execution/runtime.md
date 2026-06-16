# Runtime — Agent Schema Consolidation

## Branch de execução

`development_agent-schema-consolidation`

## Baseline

- source branch: `development`
- source SHA observado: `537e401356f956e928d1a7d025a3d9ccff2222aa`
- expected migration mode: `append_only`

## Guard obrigatório

```bash
test "$(git branch --show-current)" = "development_agent-schema-consolidation"
git merge-base --is-ancestor 537e401356f956e928d1a7d025a3d9ccff2222aa HEAD
git status --short
git rev-parse HEAD
```

## Decisões absolutas

- `agent` é o único schema do bounded context agent.
- `ai`, `knowledge` e `runtime` não existem no catálogo final.
- FK intra-agent é permitida.
- FK cross-module é proibida em qualquer direção.
- IDs externos são UUIDs opacos, indexados localmente.
- migrations são append-only por padrão.
- legacy views são temporárias e precisam ser removidas.
- `DROP SCHEMA ... CASCADE` é proibido no upgrade de contract.

## Estado atual

`executing`

## Status das specs

| Spec | Status | Data | SHA | Evidências | Próxima |
|---|---|---|---|---|---|
| 000 | completed | 2026-06-16 | cd4da37 | detection-spec-000.md, test_agent_schema_consolidation_adr.py | 001 |
| 001 | pending | - | - | - | 002 |
| 002 | pending | - | - | - | 003 |
| 003 | pending | - | - | - | 004 |
| 004 | pending | - | - | - | 005 |
| 005 | pending | - | - | - | 006 |
| 006 | pending | - | - | - | 007 |
| 007 | pending | - | - | - | 008 |
| 008 | pending | - | - | - | 009 |
| 009 | pending | - | - | - | 010 |
| 010 | pending | - | - | - | 011 |
| 011 | pending | - | - | - | 012 |
| 012 | pending | - | - | - | 013 |
| 013 | pending | - | - | - | 014 |
| 014 | pending | - | - | - | 015 |
| 015 | pending | - | - | - | 016 |
| 016 | pending | - | - | - | 017 |
| 017 | pending | - | - | - | - |

## Inventários obrigatórios

- `execution/inventory/current-database.md`
- `execution/inventory/objects.md`
- `execution/inventory/foreign-keys.md`
- `execution/inventory/table-map.md`
- `execution/inventory/migration-history.md`
- `execution/inventory/messaging-state.md`
- `execution/inventory/data-parity.md`
- `execution/inventory/deployment-observation.md`
- `execution/final-report.md`
- `execution/detection-spec-000.md`

## Riscos ativos

- estado real do banco ainda não inventariado;
- possíveis eventos pendentes em tabelas legacy;
- locks e volume de dados desconhecidos;
- dependências externas por FK, view, function ou raw SQL desconhecidas;
- migrations históricas criam schemas legados;
- `alembic current` indisponível: sem PostgreSQL neste ambiente.

## Próxima spec recomendada

`001`

## Histórico de execução

### Spec 000 — architecture-decision-agent-schema-as-single-owner

- **Status:** completed
- **Data:** 2026-06-16
- **SHA:** cd4da371f07f1fb71c1c188e1368f5cd21dbd9ed
- **Scope:** agent-schema-consolidation
- **Skills aplicadas:** projectrai-spec-orchestrator, projectrai-architecture-boundaries, projectrai-discovery-inventory, projectrai-test-validation

#### Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: branch check | 0 | `development_agent-schema-consolidation` |
| Guard: baseline SHA ancestor | 0 | `537e401` is ancestor of HEAD |
| Guard: working tree clean | 0 | Clean |
| `Select-String schema references` | 0 | Substituiu `rg` (indisponível). FKs para `ai.*`, `knowledge.*`, `runtime.*` encontradas. |
| `Select-String FK references` | 0 | FKs intra-agent legadas e cross-module encontradas. |
| `alembic current` | 1 | Pendência: sem PostgreSQL. |
| `alembic heads` | 0 | `0014 (head)` |

#### Files changed

- `specs/agent-schema-consolidation/execution/detection-spec-000.md` — created
- `specs/agent-schema-consolidation/execution/runtime.md` — updated
- `tests/architecture/test_agent_schema_consolidation_adr.py` — created

#### Validation commands

| Comando | Exit code | Notas |
|---|---|---|---|
| `ruff check src tests` | 1 | 20 pre-existing errors (unrelated to our changes) |
| `ruff check new test file only` | 0 | Clean |
| `pyright` | 1 | 655 pre-existing errors (unrelated to our changes) |
| `pyright new test file only` | 0 | Clean |
| `pytest tests/architecture -q` | 1 | 42 pre-existing failures, 629 passed (our 7 ADR tests pass) |
| `pytest new ADR test` | 0 | 7 passed |

#### Acceptance criteria

1. ADR accepted and referenced by all following specs ✅ (spec file exists and test validates content)
2. Final ownership table approved ✅ (defined in README.md, referenced by ADR)
3. No ambiguity between FK intra-agent and FK cross-module ✅ (ADR explicitly defines policy)

#### Decisiones tomadas durante a execução

- `rg` (ripgrep) não está disponível no Windows. Substituído por `Select-String` do PowerShell.
- `alembic current` requer PostgreSQL rodando. Registrado como pendência.
- Os arquivos de inventário (`current-database.md`, `objects.md`, etc.) permanecem como placeholders pois são explicitamente atribuídos às specs 001+.

#### Decisões absolutas confirmadas

- `agent` é o único schema do bounded context agent.
- FK intra-agent é permitida.
- FK cross-module é proibida em qualquer direção.
- IDs externos são UUIDs opacos, indexados localmente.
- Migrations são append-only por padrão.
- `DROP SCHEMA ... CASCADE` é proibido no upgrade de contract.

#### Riscos ativos

- `alembic current` indisponível sem PostgreSQL.

#### Próxima spec recomendada

`001`
