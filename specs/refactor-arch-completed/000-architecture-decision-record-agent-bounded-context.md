# 000 — architecture decision record agent bounded context

## Tipo

architecture

## Objetivo

Formalizar a decisão arquitetural mandatória de unificar `ai`, `knowledge` e `runtime` no bounded context `agent`, preservando modular monolith e comunicação event-driven.

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

- Nenhuma.

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

## Regra de ownership de banco decidida

A decisão inclui explicitamente o banco de dados: módulos não compartilham ownership transacional por Foreign Keys físicas entre schemas/tabelas de módulos distintos. Cada módulo pode persistir identificadores de outros módulos como valores opacos para correlação, auditoria ou referência histórica, mas não pode criar constraint física, cascade, join operacional para alteração de estado, nem depender da existência transacional do agregado externo.

Foreign Keys entre entidades oriundas de `ai`, `knowledge` e `runtime` são permitidas apenas após estarem dentro do schema/model ownership de `agent`. Foreign Keys que apontem para `ai`, `knowledge` ou `runtime` devem ser removidas no estado final junto com os schemas/módulos legados.

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

1. Criar este ADR em `/specs/000-architecture-decision-record-agent-bounded-context.md`.
2. Registrar decisão como `accepted`.
3. Registrar alternativas rejeitadas e consequências operacionais.
4. Atualizar `/specs/execution/runtime.md` com a decisão principal.
5. Validar que specs posteriores referenciam este ADR.


## Contratos esperados

- ADR id: `ADR-000-agent-bounded-context`.
- Status inicial: `accepted`.
- Decisão: `ai`, `knowledge` e `runtime` serão unificados em `agent`.
- Alternativas rejeitadas obrigatórias:
  - manter três bounded contexts;
  - criar microservices;
  - criar EventBus genérico de domínio em `shared`;
  - manter workers concretos globais em `src/workers`.
- Consequência obrigatória: `agent` passa a possuir domínio, application, infra, presentation, Outbox, Inbox, UoW e workers próprios.
- Compatibilidade temporária: shims só podem delegar para `agent` e devem ser removidos por specs 140-145.


## Testes obrigatórios

- Arquivo esperado: `tests/architecture/test_architecture_decision_record_agent_bounded_context.py` ou teste de módulo correspondente.
- Caso: `test_architecture_decision_record_agent_bounded_context_success`.
- Caso: `test_architecture_decision_record_agent_bounded_context_rejects_forbidden_dependency` quando aplicável.
- Caso: `test_architecture_decision_record_agent_bounded_context_keeps_legacy_compatibility` se shim for criado.


## Comandos de validação

```bash
ruff check src tests
pytest
pytest tests/architecture
alembic upgrade head
alembic downgrade -1
```

Se alguma ferramenta ainda não existir no inventário, registrar no `/specs/execution/runtime.md` como pendência e executar apenas os comandos confirmados.




Conteúdo normativo do ADR a registrar nesta spec:

- Contexto: o ProjectRAI apresenta separação física entre `ai`, `knowledge` e `runtime`, mas o fluxo de execução de agente exige uso simultâneo desses conceitos: carregar agente e credencial, montar prompt, buscar contexto em knowledge base, chamar LLM, persistir sessão/mensagens, registrar execução e emitir eventos. A separação física atual força imports cruzados, UoW atravessando módulos e workers globais conhecendo detalhes de domínio.
- Decisão: criar `src/modules/agent` como bounded context único para execução de agentes, runtime de sessão/mensagem/ask job, integração com LLM, knowledge base associada ao agente, releases, prompts, contratos, model configs, ferramentas internas do agente, eventos próprios, Outbox/Inbox próprias e workers concretos próprios.
- Status: `accepted`.
- Consequências: `ai`, `knowledge` e `runtime` serão depreciados, migrados e removidos; schemas/tabelas finais pertencem a `agent` após expand-migrate-contract; `metering` e `observability` deixam de ser escritos diretamente pelo fluxo do agente e passam a reagir a eventos; workers globais deixam de conter regra de negócio.
- Alternativas rejeitadas: manter três bounded contexts; criar microservices; criar EventBus genérico de domínio em `shared`; comunicação síncrona direta entre módulos para alteração de estado.
- Justificativa do nome `agent`: o produto executa, configura, versiona e observa agentes; LLM, knowledge e runtime são capacidades internas do ciclo de vida do agente.
- Justificativa Outbox/Inbox: evita dual-write entre banco e broker, permite idempotência, retry, auditoria e desacoplamento entre produtor e consumidor.
- Justificativa workers por módulo: o worker concreto conhece filas, bindings, handlers internos e repositories do próprio módulo; colocar isso em `src/workers` ou `shared/workers` viola fronteiras.

## Critérios de aceite objetivos

- Arquivo `000-architecture-decision-record-agent-bounded-context.md` existe em `/specs`.
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

