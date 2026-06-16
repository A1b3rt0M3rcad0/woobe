# 063 — move-service-to-application-layer-metering

## Tipo

refactor

## Objetivo

Migrar `service/` de `metering` para `application/dtos`, `application/use_cases` e `application/handlers`.

## Contexto

O módulo `metering` será padronizado sem perder ownership de domínio. Estado conhecido: UsageEvent, UsageDailyProject, UsageDailyAgent; tabelas metering.usage_events, metering.usage_daily_project, metering.usage_daily_agent; cross-FKs: metering.*.project_id -> core.projects.id; metering.*.agent_id -> ai.agents.id (referência legada incompatível com agent).

## Pré-condições

- 062 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/metering -maxdepth 5 -type f | sort
rg "modules\.metering|from modules\.|ForeignKey\(|event_type|UnitOfWork" src/modules/metering tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/metering/**
- tests/modules/metering/**
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

1. Mapear DTOs para application/dtos.
2. Mover use cases para application/use_cases.
3. Separar handlers de eventos recebidos.
4. Atualizar imports internos.
5. Criar shims em service/ com deprecation.
6. Proibir novas referências a service/.

## Contratos esperados

- Bounded context `metering` continua independente.
- Entidades conhecidas: UsageEvent, UsageDailyProject, UsageDailyAgent.
- Tabelas conhecidas: metering.usage_events, metering.usage_daily_project, metering.usage_daily_agent.
- Referências cross-module a tratar: metering.*.project_id -> core.projects.id; metering.*.agent_id -> ai.agents.id (referência legada incompatível com agent).
- Rotas a preservar: rotas de registro e consulta de uso/agregados, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- DTOs não dependem de FastAPI/SQLAlchemy.
- Use cases dependem de ports próprios.
- Handlers de Inbox delegam a use cases.

## Testes obrigatórios

- tests/modules/metering/unit/application/test_use_cases.py
- tests/architecture/test_no_new_metering_service_imports.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules/metering -q
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Comandos dependentes de serviços externos, banco ou RabbitMQ são condicionais à infraestrutura confirmada no inventário, mas sua não execução deve ficar registrada como pendência objetiva.

## Critérios de aceite objetivos

- application/use_cases contém casos de uso ativos
- application/dtos contém DTOs ativos
- service/ contém apenas shims ou foi removido na spec 039/049/etc.

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `063`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `064`.
