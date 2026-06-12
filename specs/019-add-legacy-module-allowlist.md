# 019 — add legacy module allowlist

## Tipo

test

## Objetivo

Executar a etapa `add-legacy-module-allowlist` da migração incremental para o bounded context `agent`.

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

- `000-architecture-decision-record-agent-bounded-context.md`
- `001-architecture-rules-modular-monolith-boundaries.md`
- `002-agent-target-directory-structure.md`
- `003-create-current-repository-inventory.md`
- `004-create-current-import-dependency-map.md`
- `008-create-current-worker-inventory.md`

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

- Criar ou alterar arquivos em `tests/architecture`, `tests/modules/agent`, `tests/workers`, `tests/messaging` conforme escopo.
- Criar fixtures em `tests/conftest.py` ou `tests/fixtures` se necessário.
- Atualizar allowlist temporária somente quando a spec permitir.


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

1. Criar infraestrutura de testes arquiteturais em `tests/architecture`.
2. Implementar parser AST para imports Python.
3. Criar allowlist temporária explícita quando aplicável.
4. Validar que violações conhecidas do legado são permitidas apenas temporariamente.
5. Registrar no runtime cada exceção permitida.


## Contratos esperados

- Diretório: `tests/architecture`.
- Arquivos esperados:
  - `tests/architecture/test_module_boundaries.py`.
  - `tests/architecture/test_shared_boundaries.py`.
  - `tests/architecture/test_worker_locations.py`.
  - `tests/architecture/test_agent_boundaries.py`.
  - `tests/architecture/legacy_import_allowlist.yaml`.
- Testes devem usar AST, não regex frágil, para imports Python.
- Allowlist temporária deve ser explícita por arquivo, import e spec de remoção.
- Estado final deve falhar se allowlist ainda permitir `ai`, `knowledge` ou `runtime`.


## Testes obrigatórios

- Diretório: `tests/architecture`.
- Arquivos esperados:
  - `tests/architecture/test_module_boundaries.py`.
  - `tests/architecture/test_shared_boundaries.py`.
  - `tests/architecture/test_worker_locations.py`.
  - `tests/architecture/test_agent_boundaries.py`.
  - `tests/architecture/legacy_import_allowlist.yaml`.
- Testes devem usar AST, não regex frágil, para imports Python.
- Allowlist temporária deve ser explícita por arquivo, import e spec de remoção.
- Estado final deve falhar se allowlist ainda permitir `ai`, `knowledge` ou `runtime`.
- Caso específico: `test_add_legacy_module_allowlist`.
- Cenário de sucesso: regra arquitetural passa com o estado permitido.
- Cenário de falha: fixture com import/localização proibida deve falhar.


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

- Arquivo `019-add-legacy-module-allowlist.md` existe em `/specs`.
- `/specs/execution/runtime.md` foi atualizado com status da spec.
- Comandos de validação confirmados no inventário executam com exit code 0 ou pendência explícita registrada.

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

