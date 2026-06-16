# 078 — add-module-unit-integration-and-contract-tests-observability

## Tipo

test

## Objetivo

Adicionar suíte de unidade, integração, transação, messaging e contrato HTTP de `observability`.

## Contexto

O módulo `observability` será padronizado sem perder ownership de domínio. Estado conhecido: Trace, TraceEvent; tabelas observability.traces, observability.trace_events; cross-FKs: observability.traces.project_id -> core.projects.id; observability.traces.agent_id -> ai.agents.id (legada); observability.traces.session_id -> runtime.sessions.id (legada); observability.trace_events.project_id -> core.projects.id.

## Pré-condições

- 077 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/observability -maxdepth 5 -type f | sort
rg "modules\.observability|from modules\.|ForeignKey\(|event_type|UnitOfWork" src/modules/observability tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/observability/**
- tests/modules/observability/**
- tests/architecture/**
- migrations/versions/* apenas quando explicitamente necessário
- execution/runtime.md

## Alterações proibidas

- não fundir bounded contexts apenas para igualar diretórios
- não criar base repository/UoW genérico com semântica de domínio
- não executar rename destrutivo de tabela ou coluna sem expand-migrate-contract
- não modificar tabelas de outro módulo
- não usar o agent como repository/service remoto
- não alterar regra de negócio de outro módulo
- não importar internals de outro módulo
- não mover domínio para shared
- não colocar worker concreto em src/workers ou shared/workers
- não alterar contrato público sem shim/deprecation e teste de compatibilidade
- não criar comunicação síncrona direta entre módulos para mudança de estado
- não criar Foreign Key física para tabela pertencente a outro módulo

## Plano de implementação

1. Cobrir domínio e use cases.
2. Cobrir repositories/UoW em PostgreSQL compatível.
3. Cobrir Outbox/Inbox e falhas parciais.
4. Cobrir concorrência e duplicidade.
5. Cobrir rotas antigas/novas durante shim.
6. Registrar coverage baseline sem impor número arbitrário.

## Contratos esperados

- Bounded context `observability` continua independente.
- Entidades conhecidas: Trace, TraceEvent.
- Tabelas conhecidas: observability.traces, observability.trace_events.
- Referências cross-module a tratar: observability.traces.project_id -> core.projects.id; observability.traces.agent_id -> ai.agents.id (legada); observability.traces.session_id -> runtime.sessions.id (legada); observability.trace_events.project_id -> core.projects.id.
- Rotas a preservar: rotas de traces e eventos de trace, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- Testes não compartilham fixtures de domínio entre módulos.
- Integração usa schema isolado ou transação limpa.

## Testes obrigatórios

- tests/modules/observability/unit/**
- tests/modules/observability/integration/**
- tests/modules/observability/contract/**

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules/observability -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- pytest tests/modules/observability retorna 0
- cenários de rollback/idempotência passam
- contratos HTTP preservados

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `078`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `079`.
