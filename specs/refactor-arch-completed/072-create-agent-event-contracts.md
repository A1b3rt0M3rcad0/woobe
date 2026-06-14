# 072 — create agent event contracts

## Tipo

messaging

## Objetivo

Definir e implementar a base transacional de Outbox/Inbox/UoW do módulo `agent` com idempotência, locks e estados verificáveis.

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

- `010-create-agent-module-skeleton.md`
- `011-create-agent-domain-layer-skeleton.md`
- `012-create-agent-application-layer-skeleton.md`
- `013-create-agent-infra-layer-skeleton.md`
- `014-create-agent-presentation-layer-skeleton.md`
- `045-update-runtime-imports-to-agent-imports.md`

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

- Criar/alterar arquivos em `shared/workers` quando forem bases genéricas.
- Criar/alterar arquivos em `src/modules/<module>/infra/workers` quando forem workers concretos.
- Criar/alterar arquivos em `src/modules/<module>/infra/messaging` para publishers/consumers/mappers do módulo.
- Criar testes de worker, retry, DLQ, ack e idempotência.


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

1. Criar/ajustar models, repositories ou políticas do `agent` conforme contrato.
2. Adicionar constraints e índices determinísticos.
3. Implementar transições de status como funções testáveis.
4. Implementar claim com lock quando aplicável.
5. Criar migrations sem remover legado.
6. Criar testes de idempotência e concorrência.
7. Atualizar runtime.


## Contratos esperados

- Arquivo: `src/modules/agent/domain/events.py`.
- Eventos mínimos:
  - `AgentExecutionRequestedV1` routing key `agent.execution.requested.v1`.
  - `AgentExecutionCompletedV1` routing key `agent.execution.completed.v1`.
  - `AgentExecutionFailedV1` routing key `agent.execution.failed.v1`.
  - `AgentKnowledgeDocumentIndexedV1` routing key `agent.knowledge.document_indexed.v1`.
  - `AgentFallbackTriggeredV1` routing key `agent.execution.fallback_triggered.v1`.
- Envelope obrigatório definido na spec 102: `event_id`, `event_type`, `event_version`, `producer_module`, `routing_key`, `occurred_at`, `payload`, `idempotency_key`, `correlation_id`, `causation_id`, `metadata`.


## Testes obrigatórios

- Arquivo esperado: `tests/modules/agent/test_create_agent_event_contracts.py`.
- Cenário de sucesso: criação/claim/transição válida conforme contrato.
- Cenário de falha: transição inválida rejeitada.
- Cenário de idempotência: duplicate `idempotency_key` não gera segundo efeito.
- Cenário de concorrência: duas tasks não reivindicam o mesmo registro.


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

- Arquivo `072-create-agent-event-contracts.md` existe em `/specs`.
- `/specs/execution/runtime.md` foi atualizado com status da spec.
- Comandos de validação confirmados no inventário executam com exit code 0 ou pendência explícita registrada.
- Constraints/índices/status/transições definidos nesta spec existem e são testados.
- Teste de idempotência aplicável passa.
- Teste de concorrência aplicável passa.

## Rollback

Reverter o commit/patch desta spec, preservar inventários já gerados e registrar rollback em `/specs/execution/runtime.md` com motivo e arquivos revertidos.

## Atualização obrigatória de runtime.md

Atualizar `/specs/execution/runtime.md` nas seções:

- `Estado atual da migração`: registrar resumo da execução.
- `Status das specs`: alterar esta spec para `completed`, `blocked` ou `skipped`.
- `Specs executadas`: adicionar entrada com data, autor/agente e resultado.
- `Decisões tomadas durante a execução`: registrar decisões novas, se houver.
- `Riscos ativos`: adicionar, atualizar ou encerrar riscos observados.
- `Inconsistências encontradas`: registrar qualquer divergência objetiva.
- `Próxima spec recomendada`: apontar a próxima spec pelo id e arquivo.

