# 134 — update alembic or database migrations

## Tipo

database

## Objetivo

Executar a etapa `update-alembic-or-database-migrations` da migração incremental para o bounded context `agent`.

## Contexto

Esta spec faz parte da migração incremental do ProjectRAI para consolidar `ai`, `knowledge` e `runtime` no bounded context `agent`. A execução deve preservar o modular monolith, impedir acoplamento cruzado e substituir dependências diretas por Outbox/Inbox quando a interação atravessar módulos distintos.

Contexto real já observado no repositório:

Estado preliminar observado no ProjectRAI em 2026-06-12:

- `src/main.py` registra diretamente os routers `modules.ai`, `modules.knowledge` e `modules.runtime`.
- `src/workers/runner.py` instancia `OutboxPublisherWorker`, `InboxConsumerWorker`, `InboxDispatcherWorker` e `AskJobWorker` diretamente.
- `src/workers/dispatcher.py` contém handlers por evento de negócio e conhece eventos de `identity`, `core`, `ai`, `knowledge` e `metering`.
- `src/shared/workers/outbox_publisher.py` e `src/shared/workers/inbox_dispatcher.py` mantêm listas fixas de módulos, incluindo `ai`, `knowledge` e `runtime`.
- `src/shared/workers/inbox_consumer.py` roteia eventos pelo primeiro segmento do `event_type`, usando uma queue global `projectrai.inbox` e import dinâmico de models do produtor.
- `src/modules/runtime/service/ask_use_case.py` importa diretamente domínio/repositórios de `ai`, `knowledge`, `metering` e `observability`.
- `src/modules/runtime/infra/ask_job_worker.py` monta um caso de uso com repositórios de `ai`, `knowledge`, `runtime`, `metering` e `observability` sob um UoW compartilhado.
- `src/modules/ai/infra/models.py`, `src/modules/knowledge/infra/models.py` e `src/modules/runtime/infra/models.py` têm schemas separados e Outbox/Inbox próprias.
- `migrations/env.py` importa explicitamente models de `ai`, `knowledge` e `runtime` para metadata do Alembic.


## Pré-condições

Specs que precisam estar concluídas:

- `045-update-runtime-imports-to-agent-imports.md`
- `063-wire-central-runner-to-module-worker-registries.md`
- `085-implement-agent-worker-registry.md`
- `100-standardize-module-outbox-pattern.md`
- `101-standardize-module-inbox-pattern.md`
- `102-standardize-event-envelope.md`
- `103-standardize-event-idempotency.md`
- `104-standardize-event-retry-policy.md`
- `105-standardize-dead-letter-policy.md`
- `106-standardize-rabbitmq-topology.md`
- `107-standardize-event-versioning-policy.md`
- `108-standardize-event-observability-and-tracing.md`
- `109-standardize-event-compatibility-policy.md`

Arquivos e inventários necessários:

- `/specs/execution/runtime.md` existente.
- `/specs/execution/inventory/files.md`, `/imports.md`, `/database-ownership.md`, `/routes.md`, `/events.md`, `/workers.md` quando esta spec depender de movimentação física.
- Branch limpa ou alterações isoladas por commit/patch.

Invariantes arquiteturais aplicáveis:

- `ai`, `knowledge` e `runtime` são legado em migração para `agent`.
- Worker concreto pertence ao módulo dono.
- Shared não contém domínio de módulo.
- UoW não atravessa fronteiras de módulo.
- Comunicação entre módulos para mudança de estado ocorre somente por eventos via Outbox/Inbox.

## Estado atual a detectar

```bash
pwd
git status --short
git branch --show-current
find src -maxdepth 4 -type f | sort | sed 's#^#- #' | head -300
find tests -maxdepth 5 -type f | sort | sed 's#^#- #' || true
rg "from modules\.(ai|knowledge|runtime)|import modules\.(ai|knowledge|runtime)" src tests || true
rg "Outbox|Inbox|Rabbit|Consumer|Dispatcher|Worker|UnitOfWork|PostgresUnitOfWork" src tests || true
```


## Alterações permitidas

- Criar/alterar models e repositories do próprio módulo alvo.
- Criar migrations Alembic em `migrations/versions`.
- Criar testes transacionais.
- Atualizar inventários e runtime.


## Alterações proibidas

- Não alterar regra de negócio de outro módulo.
- Não importar internals de outro módulo.
- Não mover domínio, entities, value objects, DTOs de domínio ou use cases para `shared`.
- Não colocar worker concreto em `src/workers`.
- Não alterar contrato público sem shim/deprecation explícito.
- Não criar comunicação síncrona direta entre módulos para mudança de estado.
- Não remover `src/modules/ai`, `src/modules/knowledge` ou `src/modules/runtime` antes das specs de depreciação/remoção.
- Não fazer rename destrutivo de tabelas sem fase expand-migrate-contract.


## Plano de implementação

1. Atualizar bootstrap, rotas, DI, settings ou migrations conforme escopo.
2. Preservar compatibilidade temporária com shims explícitos quando necessário.
3. Não remover legado nesta fase.
4. Executar testes arquiteturais, integração e migrations.
5. Atualizar runtime e inventários impactados.


## Contratos esperados

- Estratégia obrigatória: expand-migrate-contract.
- Fase expand: criar schema/tabelas/colunas `agent` sem remover `ai`, `knowledge`, `runtime`.
- Fase migrate: backfill idempotente e verificável.
- Fase dual-read/shim: rotas legadas delegam para `agent` enquanto validação ocorre.
- Fase contract: remover tabelas/schemas legados somente nas specs finais, após testes e runtime atualizado.
- Não usar rename destrutivo em big bang.



### Política obrigatória para Foreign Keys durante migrations

A estratégia expand-migrate-contract deve tratar FKs cross-module explicitamente:

1. Na fase `expand`, criar tabelas do schema `agent` com FKs somente para tabelas `agent.*`.
2. Não criar novas FKs de `agent` para `core`, `identity`, `billing`, `metering`, `tools` ou `observability`.
3. Não criar novas FKs desses módulos para `agent`.
4. Migrar `ai`, `knowledge` e `runtime` para `agent` internalizando as FKs que hoje existem entre esses três schemas. Exemplo: `runtime.sessions.agent_id -> ai.agents.id` deve virar coluna/constraint interna ao ownership `agent`, não dependência entre módulos.
5. Para relações com módulos que permanecem externos, converter FK física em coluna escalar opaca, preservar o valor do ID e remover a constraint física somente na fase contract validada.
6. Antes de remover qualquer constraint, executar query de órfãos e registrar resultado no runtime. A existência de órfãos deve bloquear a remoção silenciosa e exigir decisão explícita.
7. Proibir `ON DELETE CASCADE` entre módulos. Cascades são permitidos somente dentro do mesmo módulo.
8. Toda migration deve ter downgrade seguro em banco de teste, sem apagar dados migrados sem backup/rollback documentado.

Queries de validação esperadas em PostgreSQL:

```sql
SELECT
  conrelid::regclass AS source_table,
  confrelid::regclass AS target_table,
  conname
FROM pg_constraint
WHERE contype = 'f'
ORDER BY 1, 2, 3;
```

A execução deve classificar cada linha como `same_module` ou `cross_module`. Qualquer `cross_module` não listada como legacy temporária bloqueia a spec.

## Testes obrigatórios

- Arquivo esperado: `tests/architecture/test_update_alembic_or_database_migrations.py` ou teste de módulo correspondente.
- Caso: `test_update_alembic_or_database_migrations_success`.
- Caso: `test_update_alembic_or_database_migrations_rejects_forbidden_dependency` quando aplicável.
- Caso: `test_update_alembic_or_database_migrations_keeps_legacy_compatibility` se shim for criado.


## Comandos de validação

```bash
ruff check src tests
pytest
pytest tests/architecture
alembic upgrade head
alembic downgrade -1
```

Se alguma ferramenta ainda não existir no inventário, registrar no `/specs/execution/runtime.md` como pendência e executar apenas os comandos confirmados.


## Critérios de aceite objetivos

- Arquivo `134-update-alembic-or-database-migrations.md` existe em `/specs`.
- `/specs/execution/runtime.md` foi atualizado com status da spec.
- Comandos de validação confirmados no inventário executam com exit code 0 ou pendência explícita registrada.

## Rollback

Executar downgrade da migration criada nesta spec em banco de teste. Reverter models/repositories desta spec mantendo inventários e runtime com status `blocked` se o downgrade falhar. Não remover dados legados.

## Atualização obrigatória de runtime.md

Atualizar `/specs/execution/runtime.md` nas seções:

- `Estado atual da migração`: registrar resumo da execução.
- `Status das specs`: alterar esta spec para `completed`, `blocked` ou `skipped`.
- `Specs executadas`: adicionar entrada com data, autor/agente e resultado.
- `Decisões tomadas durante a execução`: registrar decisões novas, se houver.
- `Riscos ativos`: adicionar, atualizar ou encerrar riscos observados.
- `Inconsistências encontradas`: registrar qualquer divergência objetiva.
- `Próxima spec recomendada`: apontar a próxima spec pelo id e arquivo.

