# 053 — move-service-to-application-layer-billing

## Tipo

refactor

## Objetivo

Migrar `service/` de `billing` para `application/dtos`, `application/use_cases` e `application/handlers`.

## Contexto

O módulo `billing` será padronizado sem perder ownership de domínio. Estado conhecido: Plan, Customer, Subscription, PaymentEvent; tabelas billing.plans, billing.customers, billing.subscriptions, billing.payment_events; cross-FKs: billing.customers.organization_id -> identity.organizations.id; billing.subscriptions.organization_id -> identity.organizations.id.

## Pré-condições

- 052 completed

## Estado atual a detectar

Execute na raiz do checkout da branch `project-rai-playground_module-architecture-standardization`:

```bash
find src/modules/billing -maxdepth 5 -type f | sort
rg "modules\.billing|from modules\.|ForeignKey\(|event_type|UnitOfWork" src/modules/billing tests -g "*.py"
```

Persistir qualquer saída de inventário indicada no plano. Comando ausente no ambiente deve ser registrado como bloqueio em `execution/runtime.md`; não substituí-lo por suposição.

## Alterações permitidas

- src/modules/billing/**
- tests/modules/billing/**
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

- Bounded context `billing` continua independente.
- Entidades conhecidas: Plan, Customer, Subscription, PaymentEvent.
- Tabelas conhecidas: billing.plans, billing.customers, billing.subscriptions, billing.payment_events.
- Referências cross-module a tratar: billing.customers.organization_id -> identity.organizations.id; billing.subscriptions.organization_id -> identity.organizations.id.
- Rotas a preservar: POST/GET /billing/plans, POST /billing/subscriptions e GET /billing/organizations/{org_id}/subscription.
- UoW concreto coordena somente repositories, Inbox e Outbox do módulo.
- DTOs não dependem de FastAPI/SQLAlchemy.
- Use cases dependem de ports próprios.
- Handlers de Inbox delegam a use cases.

## Testes obrigatórios

- tests/modules/billing/unit/application/test_use_cases.py
- tests/architecture/test_no_new_billing_service_imports.py

## Comandos de validação

```bash
ruff check src tests
pyright
pytest tests/architecture -q
pytest -q
pytest tests/modules/billing -q
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

- status da spec `053`;
- data e SHA executado;
- arquivos impactados;
- decisões tomadas;
- pendências e riscos novos/resolvidos;
- evidências dos comandos de validação;
- próxima spec recomendada: `054`.
