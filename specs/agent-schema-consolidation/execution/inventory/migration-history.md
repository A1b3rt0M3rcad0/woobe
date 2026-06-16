# Histórico de migrações e modo de compatibilidade

*Populado na spec 001 via análise estática.*

## Revisões

| Revisão | Nome | Esquemas afetados |
|---|---|---|
| 0001 | create_schemas | Cria `ai`, `knowledge`, `runtime` (não cria `agent`) |
| 0002 | create_all_tables | `ai`, `knowledge`, `runtime`, `core`, `identity`, `billing`, `metering`, `observability`, `tools` |
| 0003 | add_metadata_to_provider_credentials | `ai` |
| 0004 | add_mode_to_sessions | `runtime` |
| 0005 | fix_datetime_timezones | Diversos |
| 0006 | add_ask_jobs_table | `runtime` (+ FK para `ai.agents`) |
| 0007 | create_agent_versioning_tables | `ai`, `knowledge` |
| 0008 | add_release_snapshot_fields | `ai` |
| 0009 | add_agent_release_missing_fields | `ai` |
| 0010 | add_production_unique_constraint | `ai` |
| 0011 | add_fallback_fields_to_agent_releases | `ai` |
| 0012 | make_tool_agent_id_nullable | `tools` |
| 0013 | create_agent_outbox_events | Cria schema `agent` + `agent_outbox_events` |
| 0014 | create_agent_inbox_events | `agent` + `agent_inbox_events` |

## Modo de compatibilidade

`append_only` — migrations históricas não são reescritas. Novas migrations farão `ALTER TABLE ... SET SCHEMA` e criarão views legadas temporárias.

## Head atual

`0014 (head)`

## Pendências

- Verificação de migrations aplicadas vs. registradas requer PostgreSQL.
- Fresh install precisa ser testado separadamente.
