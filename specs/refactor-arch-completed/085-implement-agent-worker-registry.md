# 085 — implement agent worker registry

## Tipo

worker

## Objetivo

Implementar workers concretos do módulo `agent` sem regra de negócio em worker, usando RabbitMQ e delegação para application layer.

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

- `050-create-shared-worker-contracts.md`
- `051-create-shared-outbox-dispatcher-base.md`
- `052-create-shared-inbox-consumer-base.md`
- `053-create-shared-inbox-processor-base.md`
- `054-create-shared-worker-runner.md`
- `055-create-shared-worker-registry-contract.md`
- `070-create-agent-outbox-model-and-repository.md`
- `071-create-agent-inbox-model-and-repository.md`
- `072-create-agent-event-contracts.md`
- `073-create-agent-event-mappers.md`
- `074-create-agent-unit-of-work.md`
- `075-create-agent-outbox-database-migration.md`
- `076-create-agent-inbox-database-migration.md`
- `077-create-agent-outbox-status-transition-policy.md`
- `078-create-agent-inbox-status-transition-policy.md`
- `079-create-agent-outbox-inbox-locking-policy.md`

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

1. Implementar worker concreto dentro de `src/modules/agent/infra/workers`.
2. Usar bases genéricas de `shared/workers` sem colocar regra de negócio nelas.
3. Fazer worker delegar para repositories/application handlers internos.
4. Implementar ack/retry/DLQ conforme política.
5. Criar testes unitários e de integração com doubles de RabbitMQ.
6. Atualizar runtime.


## Contratos esperados

- Workers concretos do `agent`:
  - `AgentOutboxDispatcherWorker` em `src/modules/agent/infra/workers/outbox_dispatcher.py`.
  - `AgentInboxConsumerWorker` em `src/modules/agent/infra/workers/inbox_consumer.py`.
  - `AgentInboxProcessorWorker` em `src/modules/agent/infra/workers/inbox_processor.py`.
  - `register_agent_workers(registry, settings, engine)` em `src/modules/agent/infra/workers/registry.py`.
- Consumers usam queues próprias do módulo consumidor, por exemplo `agent.identity-events`.
- Worker não contém regra de negócio; delega para application handlers/use cases.
- Ack RabbitMQ ocorre somente após persistência na Inbox.


## Testes obrigatórios

- Arquivo esperado: `tests/modules/agent/workers/test_implement_agent_worker_registry.py`.
- Cenário de sucesso: worker delega para repository/handler correto.
- Cenário de falha: erro transitório gera retry/backoff.
- Cenário de idempotência: evento duplicado não é processado duas vezes.
- Cenário de concorrência: dois workers não processam a mesma mensagem.
- Verificar que worker não importa domínio de outro módulo.


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

- Arquivo `085-implement-agent-worker-registry.md` existe em `/specs`.
- `/specs/execution/runtime.md` foi atualizado com status da spec.
- Comandos de validação confirmados no inventário executam com exit code 0 ou pendência explícita registrada.
- Worker concreto está em `src/modules/agent/infra/workers`.
- Worker não contém regra de negócio e delega para application layer.
- Ack/retry/DLQ/idempotência testados conforme aplicável.

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

