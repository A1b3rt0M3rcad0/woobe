# Relatório Final — Agent Schema Consolidation

## Resumo

O pacote `agent-schema-consolidation` consolidou todas as tabelas de negócio do
bounded context agent dos schemas legados `ai`, `knowledge` e `runtime` para o
schema canônico `agent`.

## Informações gerais

| Campo | Valor |
|---|---|
| Branch de execução | `development_agent-schema-consolidation` |
| Baseline | `development` @ `537e401356f956e928d1a7d025a3d9ccff2222aa` |
| SHA inicial | `73d3b63` (spec 014 blocked) |
| SHA final | (current) |
| Modo de migration | `append_only` |
| Status | `completed` |

## Specs executadas

| Spec | Status | SHA |
|---|---|---|
| 000 — Architecture Decision Record | completed | cd4da37 |
| 001 — Inventory current database and migration state | completed | 26b74b4 |
| 002 — Define target table and constraint map | completed | 18b503e |
| 003 — Define expand-migrate-contract and rollback protocol | completed | 45d5eee |
| 004 — Add temporary schema and FK architecture guards | completed | eced77e |
| 005 — Prepare agent schema and migration preflight | completed | ec24714 |
| 006 — Move ai business tables to agent schema | completed | c7f8c06 |
| 007 — Move knowledge business tables to agent schema | completed | 2d0a056 |
| 008 — Move runtime business tables to agent schema | completed | bdc6fbe |
| 009 — Update agent SQLAlchemy models and internal FKs | completed | 0b738d8 |
| 010 — Remove cross-module Foreign Keys | completed | bb24f9d |
| 011 — Consolidate legacy messaging state | completed | 333a0e1 |
| 012 — Remove runtime code references to legacy schemas | completed | 6be2ad9 |
| 013 — Update alembic head and fresh-install contract | completed | 63e1c41 |
| 014 — Data integrity and schema migration tests | completed | aaad642 |
| 015 — Application cutover and observability window | completed | 9804808 |
| 016 — Drop legacy views, tables, and schemas | completed | 6e9b1ed |
| 017 — Final validation, remove allowlists, and report | completed | (current) |

## Migrations criadas

| Migration | Descrição |
|---|---|
| 0015 | Move ai tables → agent (7 SET SCHEMA + compat views) |
| 0016 | Move knowledge tables → agent (5 SET SCHEMA + compat views) |
| 0017 | Move runtime tables → agent (3 SET SCHEMA + compat views) |
| 0018 | Remove 22 cross-module Foreign Keys |
| 0019 | Consolidate legacy messaging (drop 6 legacy tables) |
| 0020 | Drop legacy schemas (ai, knowledge, runtime) |

## Objetos movidos

### Tabelas de negócio (15)

| Tabela | Schema origem | Schema destino |
|---|---|---|
| provider_credentials | ai | agent |
| agents | ai | agent |
| agent_prompts | ai | agent |
| agent_contracts | ai | agent |
| agent_model_configs | ai | agent |
| agent_releases | ai | agent |
| agent_release_tests | ai | agent |
| document_collections | knowledge | agent |
| agent_collections | knowledge | agent |
| documents | knowledge | agent |
| document_chunks | knowledge | agent |
| knowledge_versions | knowledge | agent |
| sessions | runtime | agent |
| messages | runtime | agent |
| ask_jobs | runtime | agent |

### Tabelas de mensageria canônicas (2)

| Tabela | Schema |
|---|---|
| agent_outbox_events | agent (criada na migration 0013) |
| agent_inbox_events | agent (criada na migration 0014) |

### Eventos migrados

| Schema | Tabela | Eventos |
|---|---|---|
| ai | outbox_events | 13 → agent.agent_outbox_events |
| runtime | outbox_events | 79 → agent.agent_outbox_events |

## Constraints removidas

### Cross-module FKs (22)

| Origem | Destino | Quantidade |
|---|---|---|
| agent.* → core.projects | project_id columns | 14 |
| agent.* → identity.users | created_by/promoted_by | 3 |
| metering.* → ai.agents | agent_id | 2 |
| observability.* → ai.agents/runtime.sessions | agent_id/session_id | 2 |
| tools.* → ai.agents | agent_id | 1 |

## Estado do catálogo ao final

| Verificação | Resultado |
|---|---|
| Schemas legados (ai, knowledge, runtime) | Zero ✅ |
| Tabelas no schema agent | 17 ✅ |
| FKs intra-agent (agent→agent) | 27 ✅ |
| FKs cross-module (agent→external) | Zero ✅ |
| FKs cross-module (external→agent) | Zero ✅ |
| Alembic version | 0020 ✅ |

## Validação arquitetural

| Verificação | Resultado |
|---|---|
| Schema references em src/ | Zero ✅ |
| Legacy module imports (modules.ai/knowledge/runtime) | Zero ✅ |
| Cross-module FKs em modelos SQLAlchemy | Zero ✅ |

## Testes criados

| Arquivo | Testes | Finalidade |
|---|---|---|
| test_spec_017_final_validation.py | 12 | Validação final arquitetural e de catálogo |

## Riscos residuais

- `alembic current` CLI não funcional da máquina Windows Python 3.14
  (asyncpg/ProactorEventLoop). DB state verificado via psql no container Docker.
- Rollback após spec 016 (DROP SCHEMA) requer restore ou migration compensatória.
- 7 testes de arquitetura pré-existentes de specs 005-008 falham
  (esperado — validavam estado intermediário anterior à migração).

## Rollback disponível

Até a spec 015, rollback possível via `SET SCHEMA` reverso conforme runbook.
Após a spec 016, rollback requer restore de snapshot ou migration
compensatória. A migration 0020 possui downgrade que recria schemas e views
vazios (dados permanecem em agent.*).

## Conclusão

O pacote `agent-schema-consolidation` foi concluído com sucesso.
O schema `agent` é o único owner físico das tabelas do bounded context agent.
Todos os schemas legados (`ai`, `knowledge`, `runtime`) foram removidos.
Zero FKs cross-module permanecem. O catálogo final contém apenas `agent.*`.
