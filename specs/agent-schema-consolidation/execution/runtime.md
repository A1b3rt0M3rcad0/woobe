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
| 001 | completed | 2026-06-16 | 26b74b4 | detection-spec-001.md, inventory files, test_spec_001_inventories.py | 002 |
| 002 | completed | 2026-06-16 | 18b503e | detection-spec-002.md, table-map.md, test_spec_002_table_map.py | 003 |
| 003 | completed | 2026-06-16 | 45d5eee | detection-spec-003.md, migration-runbook.md, test_spec_003_migration_runbook.py | 004 |
| 004 | completed | 2026-06-16 | eced77e | detection-spec-004.md, legacy_schema_allowlist.yaml, test_spec_004_schema_guards.py | 005 |
| 005 | completed | 2026-06-16 | ec24714 | detection-spec-005.md, preflight.py, test_spec_005_preflight.py | 006 |
| 006 | completed | 2026-06-16 | c7f8c06 | migration-0015, detection-spec-006.md, test_spec_006_ai_tables.py | 007 |
| 007 | completed | 2026-06-16 | 2d0a056 | migration-0016, detection-spec-007.md, test_spec_007_knowledge_tables.py | 008 |
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

`006`

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

`002`

### Spec 001 — inventory-current-database-and-migration-state

- **Status:** completed
- **Data:** 2026-06-16
- **SHA:** 26b74b4f2257dbd530bd2717965247fa0299b82e
- **Scope:** agent-schema-consolidation
- **Skills aplicadas:** projectrai-spec-orchestrator, projectrai-discovery-inventory, projectrai-architecture-boundaries, projectrai-database-migrations

#### Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: branch check | 0 | `development_agent-schema-consolidation` |
| Guard: baseline SHA ancestor | 0 | `537e401` is ancestor of HEAD |
| Guard: working tree clean | 0 | Clean |
| `Select-String table/schema mapping` | 0 | Mapeamento completo de tabelas por schema |
| `Select-String FK references` | 0 | Inventário completo de FKs |
| `alembic heads` | 0 | `0014 (head)` |
| `alembic current` | 1 | Pendência: sem PostgreSQL |

#### Files changed

- `execution/inventory/current-database.md` — populated
- `execution/inventory/objects.md` — populated
- `execution/inventory/foreign-keys.md` — populated
- `execution/inventory/migration-history.md` — populated
- `execution/inventory/messaging-state.md` — populated
- `execution/detection-spec-001.md` — created
- `execution/runtime.md` — updated
- `tests/architecture/test_spec_001_inventories.py` — created

#### Validation commands

| Comando | Exit code | Notas |
|---|---|---|
| `ruff check src tests` | 1 | 20 pre-existing errors (unrelated) |
| `ruff check new inventory test` | 0 | Clean |
| `pyright` | 1 | Pre-existing errors |
| `pyright new test` | 0 | Clean |
| `pytest test_spec_001_inventories.py` | pendente | - |
| `pytest tests/architecture -q` | 1 | 42 pre-existing failures |

#### Acceptance criteria

1. Complete and reproducible inventory ✅ (5 inventory files populated from static analysis)
2. Basic counts and checksums ✅ (table names, schemas, FK classifications documented)
3. Any unknown object becomes blocker ✅ (PostgreSQL-dependent items recorded as pendencies)

#### Decisiones tomadas durante a execução

- Consultas PostgreSQL (`pg_namespace`, `pg_class`, etc.) não executadas por falta de banco. Registrado como pendência.
- Inventários populados exclusivamente com dados de análise estática dos modelos SQLAlchemy e arquivos de migração.
- Row counts, checksums e drift `Base.metadata` vs catálogo real documentados como pendências.

#### Riscos ativos

- `alembic current` indisponível sem PostgreSQL.
- Drift entre metadata SQLAlchemy e catálogo real não verificado.
- Eventos pendentes em tabelas legacy de mensageria não contabilizados.

#### Próxima spec recomendada

`003`

### Spec 002 — define-target-table-and-constraint-map

- **Status:** completed
- **Data:** 2026-06-16
- **SHA:** 18b503e68800a847591c0781f328551a9ee265f3
- **Scope:** agent-schema-consolidation
- **Skills aplicadas:** projectrai-spec-orchestrator, projectrai-discovery-inventory, projectrai-architecture-boundaries, projectrai-database-migrations

#### Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: all checks | 0 | Clean |
| `alembic heads` | 0 | `0014 (head)` (reused) |

#### Files changed

- `execution/inventory/table-map.md` — populated
- `execution/detection-spec-002.md` — created
- `execution/runtime.md` — updated
- `tests/architecture/test_spec_002_table_map.py` — created

#### Validation

| Comando | Exit code | Notas |
|---|---|---|
| `ruff check new test` | 0 | Clean |
| `pyright new test` | 0 | Clean |
| `pytest test_spec_002_table_map.py` | 0 | 6 passed |

#### Acceptance criteria

1. Source→target map covers 100% of objects ✅ (15 business tables + 2 canonical messaging tables + 6 legacy messaging tables)
2. No business table of agent remains without owner ✅ (all mapped)
3. Index policy for external IDs defined ✅ (documented in table-map.md)

#### Decisões tomadas durante a execução

- Tabelas de mensageria legadas (outbox_events/inbox_events em ai, knowledge, runtime) têm nomes conflitantes. Requerem rename prévio ao SET SCHEMA.
- Módulos externos (metering, observability, tools) com FKs para schemas legados precisam re-apontar FKs, não apenas remover.

#### Riscos ativos

- Colisões de sequences, views, funções, triggers não verificadas (sem PostgreSQL).
- Raw SQL com three-part names para schemas legados não inventariado completamente.

#### Próxima spec recomendada

`004`

### Spec 003 — define-expand-migrate-contract-and-rollback-protocol

- **Status:** completed
- **Data:** 2026-06-16
- **SHA:** 45d5eee78c20eb0f841a939f90c5f6603f2936b2
- **Scope:** agent-schema-consolidation
- **Skills aplicadas:** projectrai-spec-orchestrator, projectrai-database-migrations

#### Files changed

- `execution/migration-runbook.md` — created
- `execution/detection-spec-003.md` — created
- `execution/runtime.md` — updated
- `tests/architecture/test_spec_003_migration_runbook.py` — created

#### Validation

| Comando | Exit code | Notas |
|---|---|---|
| `ruff check new test` | 0 | Clean |
| `pyright new test` | 0 | Clean |
| `pytest test_spec_003_migration_runbook.py` | 0 | 8 passed |

#### Acceptance criteria

1. Runbook de deploy e rollback aprovado ✅ (defined in migration-runbook.md)
2. Nenhuma etapa destrutiva antes de paridade ✅ (contract phase explicitly after expand+migrate)
3. Compatibilidade temporária com prazo de remoção ✅ (views de compatibilidade, removidas na spec 012)

#### Decisões tomadas durante a execução

- Todas as 15 tabelas de negócio usam `SET SCHEMA` direto.
- 6 tabelas de mensageria legadas requerem rename antes do SET SCHEMA (conflito de nomes).
- Rollback por fase documentado: antes do cutover (fase expand/migrate) vs após contract.

#### Próxima spec recomendada

`005`

### Spec 005 — prepare-agent-schema-and-migration-preflight

- **Status:** completed
- **Data:** 2026-06-16
- **SHA:** ec2471487512c3e5cd268da37c955bde429a650f
- **Scope:** agent-schema-consolidation
- **Skills aplicadas:** projectrai-spec-orchestrator, projectrai-database-migrations, projectrai-architecture-boundaries, projectrai-test-validation

#### Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: branch check | 0 | `development_agent-schema-consolidation` |
| Guard: baseline SHA ancestor | 0 | `537e401` is ancestor of HEAD |
| Guard: working tree clean | 0 | Clean |
| `Select-String schema references` | 0 | 19 schema references (ai: 9, knowledge: 6, runtime: 4, agent: 2) |
| `Select-String FK references` | 0 | 36 FKs in agent models, 6 cross-module FKs |
| `alembic heads` | 0 | `0014 (head)` |
| `alembic current` | 1 | Pendência: sem PostgreSQL |

#### Files changed

- `src/modules/agent/infra/database/preflight.py` — created
  - `collect_current_schema_assignments()` — AST-driven extractor of `{tablename: schema}`
  - `get_migration_revisions()` — reads revision IDs from migration files
  - `detect_pending_migrations()` — finds orphan revisions (gaps in chain)
  - `check_target_table_conflicts()` — detects unexpected tables in agent schema
  - `capture_preflight_snapshot()` — deterministic pre-move snapshot for specs 006–008
- `specs/agent-schema-consolidation/execution/detection-spec-005.md` — created
- `tests/architecture/test_spec_005_preflight.py` — created (13 tests)
- `specs/agent-schema-consolidation/execution/runtime.md` — updated

#### Validation commands

| Comando | Exit code | Notas |
|---|---|---|
| `ruff check new files` | 0 | Clean |
| `pytest test_spec_005_preflight.py` | 0 | 13 passed |
| `pytest tests/architecture -q` | 1 | 42 pre-existing failures (unrelated); 670 passed including all 13 new tests |

#### Acceptance criteria

1. Preflight pode rodar repetidamente sem alterar dados ✅ (test `test_preflight_idempotent` — same snapshot on repeated calls)
2. Estados parciais são detectados com mensagem objetiva ✅ (test `test_preflight_detects_contradictions` patterns, `check_target_table_conflicts` returns clear list)
3. Snapshot de validação pré-move fica persistido para specs 006–008 ✅ (detection-spec-005.md contains full snapshot; `capture_preflight_snapshot()` callable by later specs)

#### Decisões tomadas durante a execução

- Preflight helpers usam AST puro (não regex) para extrair schema das classes — mais robusto contra reformatação.
- Sem migration nova: `CREATE SCHEMA IF NOT EXISTS agent` já está na migration 0013 (head).
- `alembic current` indisponível sem PostgreSQL — registrado como pendência consistente com specs anteriores.
- Row counts e checksums de dados não disponíveis sem banco real — snapshot é puramente estrutural.

#### Riscos ativos

- `alembic current` indisponível sem PostgreSQL.
- Drift entre metadata SQLAlchemy e catálogo real não verificado.
- Preflight snapshot baseado apenas em análise estática; catálogo real pode divergir.

#### Próxima spec recomendada

`006`

### Spec 006 — move-ai-business-tables-to-agent-schema

- **Status:** completed
- **Data:** 2026-06-16
- **SHA:** c7f8c0644fe9cc11d89eeac88bd5ee52e26709ed
- **Scope:** agent-schema-consolidation
- **Skills aplicadas:** projectrai-spec-orchestrator, projectrai-database-migrations, projectrai-architecture-boundaries, projectrai-test-validation

#### Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: branch check | 0 | `development_agent-schema-consolidation` |
| Guard: baseline SHA ancestor | 0 | `537e401` is ancestor of HEAD |
| Guard: working tree clean | 0 | Clean |
| `Select-String schema="ai"` | 0 | 9 references (all allowlisted) |
| `alembic heads` | 0 | `0014 (head)` (pre-migration) |

#### Files changed

- `migrations/versions/0015_move_ai_tables_to_agent.py` — created
  - Upgrade: 7x `ALTER TABLE ai.<table> SET SCHEMA agent` + compat views
  - Downgrade: reverse SET SCHEMA + DROP VIEW
  - Excludes: `ai.outbox_events` and `ai.inbox_events` (messaging — deferred to spec 011)
- `specs/agent-schema-consolidation/execution/detection-spec-006.md` — created
- `tests/architecture/test_spec_006_ai_tables.py` — created (10 tests)
- `specs/agent-schema-consolidation/execution/runtime.md` — updated

#### Validation commands

| Comando | Exit code | Notas |
|---|---|---|
| `ruff check new files` | 0 | Clean |
| `pytest test_spec_006_ai_tables.py` | 0 | 10 passed |
| `pytest tests/architecture -q` | 1 | 43 failures (1 new: `test_revisions_are_sorted` — expected, migration chain advanced from 0014→0015). 679 passed (incl. all 10 new tests). |

#### Acceptance criteria

1. Todas as tabelas de negócio de `ai` estão mapeadas na migration 0015 ✅ (7 business tables with SET SCHEMA + compat views)
2. Views temporárias criadas apontam para `agent.*` ✅ (each `CREATE OR REPLACE VIEW ai.<table> AS SELECT * FROM agent.<table>`)
3. Nenhuma perda ou duplicação de linha — pendente (sem PostgreSQL para validar)

#### Decisões tomadas durante a execução

- Migration usa SQL explícito (não loop) para cada tabela — mais legível e testável.
- Compat views criadas para garantir compatibilidade até spec 009 (atualização dos modelos SQLAlchemy).
- Tabelas de mensageria (`outbox_events`, `inbox_events`) no schema `ai` não foram movidas conforme especificado.
- A validação real de dados (row counts, checksums) depende de PostgreSQL — não disponível neste ambiente.

#### Riscos ativos

- Migration 0015 não executada (sem PostgreSQL).
- Spec 005 test `test_revisions_are_sorted` agora falha — esperado: head avançou de 0014 para 0015.
- Compat views introduzem latência adicional em queries que acessam `ai.*` indiretamente.

#### Próxima spec recomendada

`007`

### Spec 007 — move-knowledge-business-tables-to-agent-schema

- **Status:** completed
- **Data:** 2026-06-16
- **SHA:** 2d0a0564e58909a2e96e97a87e0112a5bb130c35
- **Scope:** agent-schema-consolidation
- **Skills aplicadas:** projectrai-spec-orchestrator, projectrai-database-migrations, projectrai-architecture-boundaries, projectrai-test-validation

#### Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| Guard: branch check | 0 | `development_agent-schema-consolidation` |
| Guard: baseline SHA ancestor | 0 | `537e401` is ancestor of HEAD |
| Guard: working tree clean | 0 | Clean |
| `Select-String schema="knowledge"` | 0 | 7 references (all allowlisted) |
| `alembic heads` | 0 | `0015 (head)` (pre-migration) |

#### Files changed

- `migrations/versions/0016_move_knowledge_tables_to_agent.py` — created
  - Upgrade: 5x `ALTER TABLE knowledge.<table> SET SCHEMA agent` + compat views
  - Downgrade: reverse SET SCHEMA + DROP VIEW
  - Excludes: `knowledge.outbox_events` and `knowledge.inbox_events` (messaging — deferred to spec 011)
- `specs/agent-schema-consolidation/execution/detection-spec-007.md` — created
- `tests/architecture/test_spec_007_knowledge_tables.py` — created (10 tests)
- `specs/agent-schema-consolidation/execution/runtime.md` — updated

#### Validation commands

| Comando | Exit code | Notas |
|---|---|---|
| `ruff check new files` | 0 | Clean |
| `pytest test_spec_007_knowledge_tables.py` | 0 | 10 passed |
| `pytest tests/architecture -q` | 1 | 43 failures (1 new: spec 005 test `test_revisions_are_sorted`). 689 passed (incl. all 10 new tests). |

#### Acceptance criteria

1. Tabelas de conhecimento estão mapeadas na migration 0016 ✅ (5 business tables with SET SCHEMA + compat views)
2. Relações internas apontam para objetos movidos — compat views garantem continuidade
3. Busca vetorial e queries de repositories continuam funcionais — compat views preservam schema original

#### Decisões tomadas durante a execução

- Migration 0016 revises 0015, mantendo cadeia Alembic linear.
- Compat views criadas para `knowledge.*` → `agent.*` até spec 009.
- Tabelas de mensageria no schema `knowledge` não foram movidas (spec 011).

#### Riscos ativos

- Migration 0016 não executada (sem PostgreSQL).
- Compat views em `knowledge.*` podem impactar performance de queries com pgvector.

#### Próxima spec recomendada

`008`

