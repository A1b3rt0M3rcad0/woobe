# 001 — architecture rules modular monolith boundaries

## Tipo

architecture

## Objetivo

Executar a etapa `architecture-rules-modular-monolith-boundaries` da migração incremental para o bounded context `agent`.

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

- Banco de dados respeita ownership por módulo: Foreign Keys físicas só podem apontar para tabelas do mesmo módulo; referências a outros módulos são IDs opacos sem constraint física.

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

- Criar/alterar arquivos em `/specs`.
- Criar/alterar testes arquiteturais apenas se explicitamente pedido por esta spec.
- Atualizar `/specs/execution/runtime.md`.


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

1. Definir matriz de imports permitidos/proibidos.
2. Definir exceção temporária por allowlist explícita.
3. Documentar mecanismo de teste AST.
4. Registrar regra absoluta de mudança de estado por API própria ou Inbox própria.
5. Atualizar runtime com invariantes.


## Contratos esperados

- Imports permitidos:
  - `modules.<same_module>.*` dentro do próprio módulo.
  - `shared.application|shared.infra|shared.presentation|shared.workers` para infraestrutura sem domínio de módulo.
  - `shared.domain.errors`, `shared.domain.time` e objetos genéricos sem linguagem específica de módulo.
- Imports proibidos:
  - `modules.<other>.domain.*`.
  - `modules.<other>.application.*`.
  - `modules.<other>.service.*`.
  - `modules.<other>.infra.models|repositories|unit_of_work|workers`.
  - `modules.<other>.presentation.*`.
- Exceção temporária: apenas imports listados em `tests/architecture/legacy_import_allowlist.yaml`.
- Mecanismo de validação: testes AST em `tests/architecture/test_module_boundaries.py`.



### Regras de banco e Foreign Keys

- Proibido declarar `ForeignKey` para schema/tabela pertencente a outro módulo.
- Proibido criar constraint `FOREIGN KEY` em migration apontando para schema de outro módulo.
- Permitido armazenar `*_id` de outro módulo apenas como coluna escalar sem constraint física.
- Permitido criar projeção local alimentada por Inbox, desde que a tabela pertença ao módulo consumidor.
- Permitido manter FKs legadas durante fases intermediárias apenas se estiverem listadas em allowlist temporária de database boundaries, com spec de remoção e registro em `/specs/execution/runtime.md`.
- Estado final não pode conter allowlist para FKs envolvendo `ai`, `knowledge` ou `runtime`.

Teste arquitetural esperado: `tests/architecture/test_database_boundaries.py`, com parser de models e migrations para detectar `ForeignKey("schema.tabela.coluna")`, `sa.ForeignKey`, `op.create_foreign_key` e constraints declaradas em SQL bruto.

## Testes obrigatórios

- Arquivo esperado: `tests/architecture/test_architecture_rules_modular_monolith_boundaries.py` ou teste de módulo correspondente.
- Caso: `test_architecture_rules_modular_monolith_boundaries_success`.
- Caso: `test_architecture_rules_modular_monolith_boundaries_rejects_forbidden_dependency` quando aplicável.
- Caso: `test_architecture_rules_modular_monolith_boundaries_keeps_legacy_compatibility` se shim for criado.


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

- Arquivo `001-architecture-rules-modular-monolith-boundaries.md` existe em `/specs`.
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

