# 153 — final architecture validation

## Tipo

validation

## Objetivo

Executar validação final objetiva da arquitetura após a migração completa.

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

- `150-final-cleanup-imports.md`
- `151-final-cleanup-dead-code.md`
- `152-final-cleanup-src-workers.md`
- `110-update-import-boundary-rules.md`
- `111-add-architecture-tests-for-module-boundaries.md`
- `112-add-architecture-tests-for-shared-layer.md`
- `113-add-architecture-tests-for-workers.md`
- `114-add-architecture-tests-for-agent-module.md`
- `120-add-agent-unit-tests.md`
- `121-add-agent-integration-tests.md`
- `122-add-outbox-dispatcher-tests.md`
- `123-add-inbox-consumer-tests.md`
- `124-add-inbox-processor-tests.md`
- `125-add-idempotency-tests.md`
- `126-add-unit-of-work-transaction-tests.md`
- `127-add-rabbitmq-publisher-confirm-tests.md`
- `128-add-inbox-deduplication-concurrency-tests.md`
- `129-add-outbox-dispatch-concurrency-tests.md`

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
```bash
rg "modules\.(ai|knowledge|runtime)" src tests || true
find src/modules -maxdepth 1 -type d | sort
find src/workers -type f -maxdepth 2 2>/dev/null || true
```


## Alterações permitidas

- Atualizar arquivos estritamente necessários ao escopo desta spec.

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

1. Executar checklist objetivo desta spec.
2. Registrar comandos, saídas relevantes e exit codes.
3. Atualizar runtime com status final.
4. Gerar relatório de validação ou migração final.
5. Bloquear conclusão se qualquer critério obrigatório falhar.


## Contratos esperados

Checklist final obrigatório:

1. `test -d src/modules/agent`.
2. `test ! -d src/modules/ai`.
3. `test ! -d src/modules/knowledge`.
4. `test ! -d src/modules/runtime`.
5. `test ! -d src/workers` ou `rg "class .*Worker|register_handler|event_type|routing_key" src/workers` sem resultados.
6. `rg "modules\.(ai|knowledge|runtime)" src tests` sem resultados.
7. `pytest tests/architecture` exit code 0.
8. `pytest tests/modules/agent` exit code 0.
9. `pytest tests/workers tests/messaging` exit code 0, se existirem.
10. `alembic upgrade head` exit code 0.
11. `alembic downgrade -1 && alembic upgrade head` exit code 0 em banco de teste.
12. Nenhum arquivo em `shared` contém entity, value object, use case, handler ou DTO de domínio de módulo.
13. RabbitMQ topology documentada e testada.
14. `runtime.md` atualizado.
15. `154-final-migration-report.md` gerado.

16. Nenhuma FK física existe entre schemas/tabelas de módulos distintos.
17. A query em `pg_constraint` para `contype = 'f'` foi executada e anexada ao relatório final com classificação `same_module` para todas as constraints restantes.
18. `rg "ForeignKey\(.*(ai|knowledge|runtime|billing|metering|identity|core|tools|observability)\." src/modules/agent src/modules/*/infra migrations` não encontra FK cross-module proibida.
19. `tests/architecture/test_database_boundaries.py` passa com a allowlist final vazia.


## Testes obrigatórios

- Arquivo esperado: `tests/architecture/test_final_architecture_validation.py` ou teste de módulo correspondente.
- Caso: `test_final_architecture_validation_success`.
- Caso: `test_final_architecture_validation_rejects_forbidden_dependency` quando aplicável.
- Caso: `test_final_architecture_validation_keeps_legacy_compatibility` se shim for criado.


## Comandos de validação

```bash
ruff check src tests
pytest
pytest tests/architecture
alembic upgrade head
alembic downgrade -1
```

Se alguma ferramenta ainda não existir no inventário, registrar no `/specs/execution/runtime.md` como pendência e executar apenas os comandos confirmados.



### Comandos adicionais obrigatórios para database boundaries

```bash
pytest tests/architecture/test_database_boundaries.py
rg "ForeignKey\(.*(ai|knowledge|runtime)\." src tests migrations || true
rg "op.create_foreign_key|FOREIGN KEY" migrations src/modules || true
```

Em banco de teste PostgreSQL, executar a query de `pg_constraint` definida na spec `134` e registrar saída em `/specs/execution/final-database-constraints.md`.

## Critérios de aceite objetivos

- Arquivo `153-final-architecture-validation.md` existe em `/specs`.
- `/specs/execution/runtime.md` foi atualizado com status da spec.
- Comandos de validação confirmados no inventário executam com exit code 0 ou pendência explícita registrada.
- Todos os 30 critérios finais de validação definidos no pacote foram verificados.
- Nenhuma allowlist temporária permanece ativa para `ai`, `knowledge` ou `runtime`.
- Relatório de falhas, se houver, foi registrado como blocker no runtime.

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

