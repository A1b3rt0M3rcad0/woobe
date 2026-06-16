# Runbook de Migração — Expand-Migrate-Contract

*Definido na spec 003.*

## Estratégia

Expand-Migrate-Contract em 3 fases, com migrations append-only.

## Fase Expand (specs 004-008)

1. Migration pré-move: criar índices, ajustar constraints, remover FKs cross-module programaticamente.
2. Executar `ALTER TABLE <legacy>.<table> SET SCHEMA agent` para cada tabela de negócio.
3. Criar views de compatibilidade no schema legado quando necessário.
4. Renomear tabelas de mensageria legadas (outbox_events → legacy_outbox_events) para evitar colisão.

### Tabelas de negócio (SET SCHEMA direto)

| Tabela | Operação | Lock estimado |
|---|---|---|
| `ai.provider_credentials` | `ALTER TABLE ai.provider_credentials SET SCHEMA agent` | AccessExclusiveLock curto |
| `ai.agents` | `ALTER TABLE ai.agents SET SCHEMA agent` | AccessExclusiveLock curto |
| `ai.agent_prompts` | `ALTER TABLE ai.agent_prompts SET SCHEMA agent` | AccessExclusiveLock curto |
| `ai.agent_contracts` | `ALTER TABLE ai.agent_contracts SET SCHEMA agent` | AccessExclusiveLock curto |
| `ai.agent_model_configs` | `ALTER TABLE ai.agent_model_configs SET SCHEMA agent` | AccessExclusiveLock curto |
| `ai.agent_releases` | `ALTER TABLE ai.agent_releases SET SCHEMA agent` | AccessExclusiveLock curto |
| `ai.agent_release_tests` | `ALTER TABLE ai.agent_release_tests SET SCHEMA agent` | AccessExclusiveLock curto |
| `knowledge.document_collections` | `ALTER TABLE knowledge.document_collections SET SCHEMA agent` | AccessExclusiveLock curto |
| `knowledge.agent_collections` | `ALTER TABLE knowledge.agent_collections SET SCHEMA agent` | AccessExclusiveLock curto |
| `knowledge.documents` | `ALTER TABLE knowledge.documents SET SCHEMA agent` | AccessExclusiveLock curto |
| `knowledge.document_chunks` | `ALTER TABLE knowledge.document_chunks SET SCHEMA agent` | AccessExclusiveLock curto |
| `knowledge.knowledge_versions` | `ALTER TABLE knowledge.knowledge_versions SET SCHEMA agent` | AccessExclusiveLock curto |
| `runtime.sessions` | `ALTER TABLE runtime.sessions SET SCHEMA agent` | AccessExclusiveLock curto |
| `runtime.messages` | `ALTER TABLE runtime.messages SET SCHEMA agent` | AccessExclusiveLock curto |
| `runtime.ask_jobs` | `ALTER TABLE runtime.ask_jobs SET SCHEMA agent` | AccessExclusiveLock curto |

### Tabelas de mensageria (rename + SET SCHEMA)

| Tabela | Operação 1 | Operação 2 |
|---|---|---|
| `ai.outbox_events` | `ALTER TABLE ai.outbox_events RENAME TO legacy_outbox_events` | `ALTER TABLE ai.legacy_outbox_events SET SCHEMA agent` |
| `ai.inbox_events` | `ALTER TABLE ai.inbox_events RENAME TO legacy_inbox_events` | `ALTER TABLE ai.legacy_inbox_events SET SCHEMA agent` |
| `knowledge.outbox_events` | `ALTER TABLE knowledge.outbox_events RENAME TO legacy_outbox_events` | `ALTER TABLE knowledge.legacy_outbox_events SET SCHEMA agent` |
| `knowledge.inbox_events` | `ALTER TABLE knowledge.inbox_events RENAME TO legacy_inbox_events` | `ALTER TABLE knowledge.legacy_inbox_events SET SCHEMA agent` |
| `runtime.outbox_events` | `ALTER TABLE runtime.outbox_events RENAME TO legacy_outbox_events` | `ALTER TABLE runtime.legacy_outbox_events SET SCHEMA agent` |
| `runtime.inbox_events` | `ALTER TABLE runtime.inbox_events RENAME TO legacy_inbox_events` | `ALTER TABLE runtime.legacy_inbox_events SET SCHEMA agent` |

## Fase Migrate (specs 009-012)

1. Atualizar modelos SQLAlchemy: `schema="agent"` para todas as tabelas.
2. Atualizar FKs internas para `agent.* -> agent.*`.
3. Remover FKs cross-module (manter colunas UUID com índices).
4. Remover views de compatibilidade após cutover de código.
5. Consolidar mensageria (unificar legado em agent_outbox_events / agent_inbox_events).

## Fase Contract (specs 013-016)

1. Atualizar head do Alembic.
2. Testar fresh install vs upgrade incremental.
3. Cutover de aplicação.
4. Observar e validar.
5. Dropar schemas legados sem CASCADE.

## Política de Locks

- `lock_timeout`: 2s por `SET SCHEMA`.
- `statement_timeout`: 30s por migration.
- Janela de manutenção: fora do horário comercial (definir por ambiente).
- Backup/snapshot obrigatório antes da execução.
- Se `lock_timeout` for atingido, abortar a migration e reverter.

## Política de Views de Compatibilidade

- Criar apenas quando houver dependência de código não atualizado na mesma release.
- Nomenclatura: `ai.<table>` como view para `agent.<table>`.
- Remover na spec 012 (ou na release seguinte ao cutover).
- Validar INSERT/UPDATE/DELETE/RETURNING pela view antes de ativar.

## Rollback por Fase

### Fase Expand (antes do cutover de código)

1. Para cada tabela movida: `ALTER TABLE agent.<table> SET SCHEMA <legado>`.
2. Remover views de compatibilidade se existirem.
3. Reverter renome de tabelas legadas.
4. Reaplicar FKs removidas (se registradas).

### Fase Migrate (após cutover de código, antes do contract)

1. Reverter código para versão anterior.
2. Mover tabelas de volta com `SET SCHEMA`.
3. Reaplicar FKs.
4. Restaurar views.
5. Validar paridade.

### Fase Contract (após drop dos schemas)

1. Rollback apenas via restore de snapshot.
2. Migration compensatória pode recriar schemas e mover tabelas de volta, mas requer teste explícito.

## Critério de Abort

Qualquer uma das condições abaixo ABORTA a execução:
- Lock_timeout excedido.
- Paridade de dados falha após move.
- View de compatibilidade não suporta DML necessário.
- Drift inesperado entre metadata e catálogo real.
- Número de eventos pendentes em tabelas legadas excede limite operacional.
