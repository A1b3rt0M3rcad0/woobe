# 005 — create current database ownership map

## Tipo

discovery

## Objetivo

Produzir inventário objetivo do estado real do repositório antes de qualquer migração física.

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
rg "__tablename__|__table_args__|ForeignKey|UniqueConstraint|Index" src/modules migrations
```


## Alterações permitidas

- Criar ou atualizar arquivos em `/specs/execution/inventory`.
- Atualizar `/specs/execution/runtime.md`.
- Criar scripts temporários de inspeção em `/tmp` ou `/specs/execution/scripts` se necessário.


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

1. Inspecionar `src/modules/*/infra/models.py` e demais arquivos de models.
2. Extrair `__tablename__`, `__table_args__`, schema, FKs, unique constraints e índices.
3. Mapear ownership de cada tabela por módulo.
4. Marcar FKs entre `ai`, `knowledge` e `runtime` como candidatas à unificação em `agent`.
5. Marcar FKs para outros módulos como dependências externas que não autorizam escrita direta.
6. Persistir resultado em `/specs/execution/inventory/database-ownership.md`.

7. Classificar cada FK como `intra_module`, `legacy_ai_knowledge_runtime_unification`, `cross_module_blocker` ou `external_reference_without_constraint`.
8. Para cada FK `cross_module_blocker`, registrar owner, tabela origem, coluna origem, tabela destino, arquivo/migration de origem, risco e spec responsável por remover/substituir por referência opaca ou projeção via eventos.
9. Gerar seção explícita `Cross-module foreign keys to remove before final state`.


## Contratos esperados

- Arquivo obrigatório de saída: `/specs/execution/inventory/database-ownership.md`.
- Conteúdo mínimo: mapa de tabelas, schemas, FKs, models e owners.

- O inventário deve distinguir FK física de coluna `*_id` sem constraint.
- O inventário deve declarar que FK física cross-module é incompatível com o estado final e deve ser removida ou internalizada no `agent` se fizer parte de `ai|knowledge|runtime`.
- Se informação estiver ausente: registrar comando executado, evidência de ausência, risco de prosseguir e próxima ação recomendada.
- O inventário deve citar caminhos reais, símbolos reais e linhas aproximadas quando viável.
- O inventário não pode conter suposições sem marcação `não confirmado`.


## Testes obrigatórios

- Arquivo esperado: `tests/architecture/test_specs_inventory_outputs.py`.
- Caso: `test_create_current_database_ownership_map_output_exists` deve validar existência do arquivo de inventário desta spec.
- Caso: `test_create_current_database_ownership_map_output_has_no_placeholder_only_content` deve falhar se o arquivo contiver apenas cabeçalho sem evidências.
- Cenário de falha: inventário ausente ou sem comandos executados.


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

- Arquivo `005-create-current-database-ownership-map.md` existe em `/specs`.
- `/specs/execution/runtime.md` foi atualizado com status da spec.
- Comandos de validação confirmados no inventário executam com exit code 0 ou pendência explícita registrada.
- Inventário `database-ownership.md` criado com evidências reais e comandos executados.

## Rollback

Remover apenas o arquivo de inventário gerado por esta spec e reverter a entrada correspondente no runtime. Nenhum código de aplicação deve ter sido alterado.

## Atualização obrigatória de runtime.md

Atualizar `/specs/execution/runtime.md` nas seções:

- `Estado atual da migração`: registrar resumo da execução.
- `Status das specs`: alterar esta spec para `completed`, `blocked` ou `skipped`.
- `Specs executadas`: adicionar entrada com data, autor/agente e resultado.
- `Decisões tomadas durante a execução`: registrar decisões novas, se houver.
- `Riscos ativos`: adicionar, atualizar ou encerrar riscos observados.
- `Inconsistências encontradas`: registrar qualquer divergência objetiva.
- `Próxima spec recomendada`: apontar a próxima spec pelo id e arquivo.

