# 062 — move-and-normalize-domain-layer-metering

## Tipo

refactor

## Objetivo

Mover e normalizar o domínio de `metering` para o contrato canônico.

## Contexto

O módulo `metering` será padronizado sem perder ownership de domínio. Estado conhecido: UsageEvent, UsageDailyProject, UsageDailyAgent; tabelas metering.usage_events, metering.usage_daily_project, metering.usage_daily_agent; cross-FKs: metering.*.project_id -> core.projects.id; metering.*.agent_id -> ai.agents.id (referência legada incompatível com agent).

## Pré-condições

- 061 completed

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

1. Mover entities/enums/errors/repository interfaces.
2. Extrair value objects apenas quando houver invariantes.
3. Definir domain events próprios.
4. Remover imports de infra/application.
5. Criar shims de import temporários se necessário.

## Contratos esperados

- Bounded context `metering` continua independente.
- Entidades conhecidas: UsageEvent, UsageDailyProject, UsageDailyAgent.
- Tabelas conhecidas: metering.usage_events, metering.usage_daily_project, metering.usage_daily_agent.
- Referências cross-module a tratar: metering.*.project_id -> core.projects.id; metering.*.agent_id -> ai.agents.id (referência legada incompatível com agent).
- Rotas a preservar: rotas de registro e consulta de uso/agregados, conforme inventário.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- domain/entities.py contém ou reexporta temporariamente UsageEvent, UsageDailyProject, UsageDailyAgent.
- domain/repositories.py contém apenas Protocol/ABC do módulo.

## Testes obrigatórios

- tests/modules/metering/unit/domain/test_entities.py
- tests/architecture/test_metering_domain_dependencies.py

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

- domain não importa SQLAlchemy/FastAPI
- interfaces concretas não estão no domínio
- invariantes cobertas por testes

## Rollback

1. Restaurar paths antigos a partir do commit anterior.
2. Reativar shim/route anterior.
3. Executar downgrade apenas para migration criada nesta spec e validada como reversível.

## Atualização obrigatória de runtime.md

Atualizar `/specs/module-architecture-standardization/execution/runtime.md` com:

- status da spec `062`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `063`.
