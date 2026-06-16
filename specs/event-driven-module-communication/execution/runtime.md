# Execution Runtime

## Suite

`specs/event-driven-module-communication`

## Branch

- Baseline: `development` @ `cd8d5867967fea25ea170bd88ebc9a461ed16c09`
- Execução: `development_event-driven-module-communication`

## Estado atual

Inventário completo de imports cross-module, writes diretos, FKs, workers e eventos. Nenhuma alteração produtiva.

## Status

| Spec | Status |
|---|---|
| 000 | completed |
| 001 | completed |
| 002 | pending |
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

## Decisões tomadas durante a execução

- Agent→Tool permanece síncrono interno (Tool já está em modules.agent)
- Agent→Metering e Agent→Observability devem usar Outbox/Inbox
- Consistência eventual para projeções e métricas
- Nenhuma alteração produtiva nesta spec ou na anterior
- Inventário completo de todas as violações classificado por severidade e spec de correção

## Riscos ativos

- A development pode avançar e exigir novo inventário.
- Consumidores externos podem depender de eventos legados.
- Payloads de Tool/LLM podem conter dados sensíveis.
- WorkerRunner não está iniciado no bootstrap atual.
- Metering/observability não possuem pipeline RabbitMQ funcional.
- FKs reais exigem inspeção em banco.
- Imports dinâmicos cross-module criam acoplamento invisível (difícil de detectar staticamente)

## Próxima spec

`002-define-target-event-flow-and-subscription-matrix.md`
