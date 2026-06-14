# 142 — deprecate runtime module

## Tipo

cleanup

## Objetivo

Executar a etapa `deprecate-runtime-module` da migração incremental para o bounded context `agent`.

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

- `130-update-application-bootstrap.md`
- `131-update-api-routes-to-agent.md`
- `132-update-dependency-injection-bindings.md`
- `133-update-settings-and-config.md`
- `134-update-alembic-or-database-migrations.md`
- `110-update-import-boundary-rules.md`
- `111-add-architecture-tests-for-module-boundaries.md`
- `112-add-architecture-tests-for-shared-layer.md`
- `113-add-architecture-tests-for-workers.md`
- `114-add-architecture-tests-for-agent-module.md`

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

- Criar/alterar arquivos do módulo `agent` e shims temporários explicitamente necessários.
- Atualizar imports, composers, routes, bootstrap, migrations e testes associados ao escopo.
- Atualizar `/specs/execution/runtime.md` e inventários impactados.


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

1. Validar pré-requisitos de remoção/depreciação.
2. Atualizar ou remover shims conforme escopo.
3. Remover imports mortos e arquivos sem uso.
4. Executar busca `rg` para garantir ausência de dependências legadas.
5. Executar testes finais aplicáveis.
6. Atualizar runtime.


## Contratos esperados

- Marcar `src/modules/runtime` como deprecated.
- Shims permitidos apenas para imports/rotas legadas e devem delegar para `agent`.
- Deve existir teste que prova compatibilidade temporária.
- Deve existir item no runtime com spec de remoção.


## Testes obrigatórios

- Arquivo esperado: `tests/architecture/test_deprecate_runtime_module.py` ou teste de módulo correspondente.
- Caso: `test_deprecate_runtime_module_success`.
- Caso: `test_deprecate_runtime_module_rejects_forbidden_dependency` quando aplicável.
- Caso: `test_deprecate_runtime_module_keeps_legacy_compatibility` se shim for criado.


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

- Arquivo `142-deprecate-runtime-module.md` existe em `/specs`.
- `/specs/execution/runtime.md` foi atualizado com status da spec.
- Comandos de validação confirmados no inventário executam com exit code 0 ou pendência explícita registrada.

## Rollback

Restaurar arquivos removidos a partir do commit anterior, reativar shims temporários se ainda existirem consumidores legados e marcar a spec como `blocked` no runtime.

## Atualização obrigatória de runtime.md

Atualizar `/specs/execution/runtime.md` nas seções:

- `Estado atual da migração`: registrar resumo da execução.
- `Status das specs`: alterar esta spec para `completed`, `blocked` ou `skipped`.
- `Specs executadas`: adicionar entrada com data, autor/agente e resultado.
- `Decisões tomadas durante a execução`: registrar decisões novas, se houver.
- `Riscos ativos`: adicionar, atualizar ou encerrar riscos observados.
- `Inconsistências encontradas`: registrar qualquer divergência objetiva.
- `Próxima spec recomendada`: apontar a próxima spec pelo id e arquivo.

