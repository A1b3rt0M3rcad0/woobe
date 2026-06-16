# Worker Topology

Levantamento em: 2026-06-16

## Agent workers

| Worker | Arquivo | Status |
|---|---|---|
| AgentWorkerRegistry | agent/infra/workers/registry.py | Activo |
| outbox_dispatcher | agent/infra/workers/outbox_dispatcher.py | Activo |
| inbox_consumer | agent/infra/workers/inbox_consumer.py | Activo |
| inbox_processor | agent/infra/workers/inbox_processor.py | Activo |
| ask_job_worker | agent/infra/workers/ask_job_worker.py | Activo (contém cross-module writes) |

## Billing workers

| Worker | Arquivo | Status |
|---|---|---|
| registry | billing/infra/workers/registry.py | Activo |
| inbox_consumer | billing/infra/workers/inbox_consumer.py | **pass (no-op)** — apenas varre tabela |

## Core workers

| Worker | Arquivo | Status |
|---|---|---|
| inbox_consumer | core/infra/workers/inbox_consumer.py | **pass (no-op)** — apenas varre tabela |

## Identity workers

| Worker | Arquivo | Status |
|---|---|---|
| registry | identity/infra/workers/registry.py | Activo |
| inbox_consumer | identity/infra/workers/inbox_consumer.py | **pass (no-op)** — apenas varre tabela |

## Metering workers

| Worker | Arquivo | Status |
|---|---|---|
| registry | metering/infra/workers/registry.py | **pass (no-op)** |
| inbox_consumer | metering/infra/workers/inbox_consumer.py | Activo |

## Observability workers

| Worker | Arquivo | Status |
|---|---|---|
| registry | observability/infra/workers/registry.py | **pass (no-op)** |
| inbox_consumer | observability/infra/workers/inbox_consumer.py | Activo |

## Inbox handlers (messaging layer)

| Módulo | Handler | Status |
|---|---|---|
| agent | inbox_handlers.py | Activo — tem handler real |
| billing | inbox_handlers.py | **No handler registered** / Routing event apenas |
| core | inbox_handlers.py | **No handler registered** / Routing event apenas |
| identity | inbox_handlers.py | **No handler registered** / Routing event apenas |
| metering | inbox_handlers.py | **No handler registered** / Routing event apenas |
| observability | inbox_handlers.py | **No handler registered** / Routing event apenas |

## Classificação

| Item | Problema | Severidade | Spec |
|---|---|---|---|
| billing inbox_consumer | pass (no-op) | média | 016 |
| core inbox_consumer | pass (no-op) | média | 016 |
| identity inbox_consumer | pass (no-op) | média | 016 |
| metering registry | pass (no-op) | média | 012 |
| observability registry | pass (no-op) | média | 014 |
| billing inbox_handlers | No handler registered | média | 016 |
| core inbox_handlers | No handler registered | média | 016 |
| identity inbox_handlers | No handler registered | média | 016 |
| metering inbox_handlers | No handler registered | alta | 012 |
| observability inbox_handlers | No handler registered | alta | 014 |
