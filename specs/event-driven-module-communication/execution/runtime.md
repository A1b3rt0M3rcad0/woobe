# Execution Runtime

## Suite

`specs/event-driven-module-communication`

## Branch

- Baseline: `development` @ `cd8d5867967fea25ea170bd88ebc9a461ed16c09`
- Execução: `development_event-driven-module-communication`

## Estado atual

Matriz alvo de eventos, ownership e subscriptions definida. Fluxos cross-module mapeados. Nenhuma alteração produtiva.

## Status

| Spec | Status |
|---|---|
| 000 | completed |
| 001 | completed |
| 002 | completed |
| 003 | pending |
| 004 | pending |
| 005 | pending |
| 006 | pending |
| 007 | pending |
| 008 | pending |
| 009 | pending |
| 010 | pending |
| 011 | pending |
| 012 | pending |
| 013 | pending |
| 014 | pending |
| 015 | pending |
| 016 | pending |
| 017 | pending |
| 018 | pending |
| 019 | pending |

## Specs executadas

### 000 — ADR — comunicação cross-module por eventos transacionais

**Status:** completed
**Tipo:** architecture
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `Select-String cross-module imports` | 0 |
| `Select-String MeteringUsageRecorder/ObservabilityTraceRecorder/AgentToolExecutor` | 0 |

**Files changed:**
- `000-adr-transactional-event-driven-module-communication.md` — status: pending → accepted
- `execution/inventory/decision-log.md` — ADR evidence recorded
- `execution/runtime.md` — runtime updated

**Validation:** Python script check — passed (key terms present)

### 001 — Inventário de imports, writes, eventos, workers e FKs

**Status:** completed
**Tipo:** discovery
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `Select-String cross-module imports in src/modules` | 0 |
| `Select-String ForeignKey cross-module in src/modules, migrations` | 0 |
| `Select-String routing_keys/queue_name/event_type in src/modules` | 0 |
| `Select-String no-op handlers in infra/messaging, infra/workers` | 0 |

**Files changed:**
- `execution/inventory/cross-module-imports.md` — inventário completo
- `execution/inventory/cross-module-writes.md` — inventário completo
- `execution/inventory/foreign-keys.md` — inventário completo
- `execution/inventory/worker-topology.md` — inventário completo
- `execution/inventory/event-catalog-current.md` — inventário completo
- `execution/runtime.md` — runtime updated

**Validation:** `test -s` for all 5 inventory files — passed

**Descobertas principais:**
- 3 arquivos com imports dinâmicos cross-module (agent → metering, agent → observability)
- 2 adapters com writes diretos cross-module compartilhando UoW do agent
- 6 FKs cross-module: billing→identity (2), metering→core (3), observability→core (2), migration→core (1)
- 3 inbox_consumers com `pass` (billing, core, identity)
- 2 registries com `pass` (metering, observability)
- 5 inbox_handlers sem handler real registrado (billing, core, identity, metering, observability)
- Eventos versionados (.v1) apenas nos domain events do agent; demais sem versão explícita

### 002 — Matriz alvo de eventos, ownership e subscriptions

**Status:** completed
**Tipo:** architecture
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `Select-String _INBOX_ROUTING_KEYS/register_*_workers/HANDLED_EVENTS in src/modules` | 0 |

**Files changed:**
- `execution/inventory/event-flow-target.md` — fluxo alvo definido
- `execution/inventory/subscription-matrix.md` — subscriptions alvo definidas
- `execution/inventory/event-payload-policy.md` — política de payload definida
- `execution/inventory/compatibility-map.md` — mapa de compatibilidade definido
- `execution/runtime.md` — runtime updated

**Validation:** `test -s` for event-flow-target, subscription-matrix, event-payload-policy — passed

**Descobertas principais:**
- Cada módulo se inscreve no próprio prefixo (`agent.#`, `billing.#`, etc.) — self-subscriptions generalizadas
- Agent: self-subscription justificada para tool events + legacy map `tools.*` → `agent.*`
- Billing/core/identity: self-subscriptions sem caso de uso real
- Metering/observability: registries vazios (`pass`), sem subscriptions reais
- HANDLED_EVENTS em cada módulo lista apenas eventos do próprio módulo (self-events)
- Nenhum módulo subscreve eventos de outro módulo atualmente

**Decisões:**
- Agent mantém self-subscription para tool events (justificada: Tool lifecycle interno)
- Metering subscreverá `agent.execution.*` para fatos quantificáveis
- Observability subscreverá `agent.execution.*` para tracing
- Billing/core/identity: remover self-subscriptions ou justificar com caso de uso real

## Decisões tomadas durante a execução

- Agent→Tool permanece síncrono interno (Tool já está em modules.agent)
- Agent→Metering e Agent→Observability devem usar Outbox/Inbox
- Consistência eventual para projeções e métricas
- Nenhuma alteração produtiva nas specs 000-002
- Inventário completo de todas as violações classificado por severidade e spec de correção
- Matriz alvo define subscriptions concretas para metering e observability
- Agent mantém self-subscription para tool events (justificada)
- Identity/core/billing: self-subscriptions a serem removidas ou justificadas

## Riscos ativos

- A development pode avançar e exigir novo inventário.
- Consumidores externos podem depender de eventos legados.
- Payloads de Tool/LLM podem conter dados sensíveis.
- WorkerRunner não está iniciado no bootstrap atual.
- Metering/observability não possuem pipeline RabbitMQ funcional.
- FKs reais exigem inspeção em banco.
- Imports dinâmicos cross-module criam acoplamento invisível (difícil de detectar staticamente)
- Remoção de self-subscriptions billing/core/identity pode impactar consumidores não documentados

## Próxima spec

`003-add-characterization-and-architecture-guards.md`
