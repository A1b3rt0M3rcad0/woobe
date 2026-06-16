# Execution Runtime

## Suite

`specs/event-driven-module-communication`

## Branch

- Baseline: `development` @ `cd8d5867967fea25ea170bd88ebc9a461ed16c09`
- Execução: `development_event-driven-module-communication`

## Estado atual

Envelope canônico IntegrationEvent criado em shared/messaging com serializer/deserializer. Outbox/Inbox padronizados com campos canônicos (routing_key, idempotency_key, locks, metadata) e constraints por módulo. Migration 0024 adiciona colunas às tabelas existentes.

## Status

| Spec | Status |
|---|---|
| 000 | completed |
| 001 | completed |
| 002 | completed |
| 003 | completed |
| 004 | completed |
| 005 | completed |
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

### 003 — Testes de caracterização e guards arquiteturais

**Status:** completed
**Tipo:** testing
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `Get-ChildItem tests -Recurse | sort` | 0 |
| `pytest --collect-only -q` | 0 |
| `Select-String architecture/outbox/inbox/rabbit/metering/observability/ask_stream in tests` | 0 |

**Files changed:**
- `tests/architecture/test_event_dynamic_imports.py` — guard de imports dinâmicos cross-module
- `tests/architecture/test_event_self_subscriptions.py` — guard de self-subscriptions
- `tests/architecture/test_event_handler_noop.py` — guard de handlers no-op
- `tests/architecture/test_event_versioning.py` — guard de versionamento de eventos
- `execution/runtime.md` — runtime updated

**Validation:** `pytest tests/architecture/test_event_dynamic_imports.py test_event_self_subscriptions.py test_event_handler_noop.py test_event_versioning.py -q` — 8 passed

**Descobertas principais:**
- 3 arquivos com imports dinâmicos cross-module (agent→metering, agent→observability) — congelados no allowlist
- 3 módulos com self-subscriptions não justificadas (billing, core, identity) — congelados
- 5 módulos com handlers no-op (billing, core, identity, metering, observability) — congelados
- 7 arquivos com eventos não versionados nas use cases do agent — congelados
- Domain events do agent (events.py) já estão versionados (.v1) corretamente

### 004 — Envelope canônico de IntegrationEvent

**Status:** completed
**Tipo:** messaging
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `Get-ChildItem event_mappers files` | 0 |
| `Read agent event_mappers (first 220 lines)` | 0 |

**Files changed:**
- `src/shared/messaging/event_envelope.py` — IntegrationEvent, serializer/deserializer adicionados
- `tests/contract/events/test_integration_event_envelope.py` — testes de contrato (round trip, inválido, idempotência, versão, redaction)
- `tests/unit/shared/test_event_envelope.py` — testes unitários do envelope e serializer
- `execution/runtime.md` — runtime updated

**Validation:** `ruff check src/shared/messaging tests/unit/shared tests/contract/events` — passed; `pytest tests/unit/shared/test_event_envelope.py tests/contract/events/test_integration_event_envelope.py -q` — 26 passed

**Descobertas principais:**
- EventEnvelope já existia como wire format — IntegrationEvent adicionado como classe de domínio canônica
- Serializer/deserializer com suporte a dict e JSON
- message_id = event_id (UUID) para deduplicação
- Idempotency key determinística via compute_idempotency_key (SHA256)
- Validação de event_type, routing_key, producer, version, idempotency
- Causation chain preservada

## Decisões tomadas durante a execução

- Agent→Tool permanece síncrono interno (Tool já está em modules.agent)
- Agent→Metering e Agent→Observability devem usar Outbox/Inbox
- Consistência eventual para projeções e métricas
- Nenhuma alteração produtiva nas specs 000-003; spec 004 adiciona IntegrationEvent canônico
- IntegrationEvent mantido em shared/messaging/ (infraestrutura genérica, sem regra de domínio)
- message_id = event_id para garantir rastreabilidade

## Riscos ativos

- A development pode avançar e exigir novo inventário.
- Consumidores externos podem depender de eventos legados.
- Payloads de Tool/LLM podem conter dados sensíveis.
- WorkerRunner não está iniciado no bootstrap atual.
- Metering/observability não possuem pipeline RabbitMQ funcional.
- FKs reais exigem inspeção em banco.
- Imports dinâmicos cross-module criam acoplamento invisível (difícil de detectar staticamente)
- Remoção de self-subscriptions billing/core/identity pode impactar consumidores não documentados
- Testes de guard dependem de allowlists que precisam ser removidas nas specs corretas
- IntegrationEvent precisa ser adotado pelos módulos (specs 007-015)

## Specs executadas

### 005 — Persistência canônica de Outbox e Inbox

**Status:** completed
**Tipo:** database
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `Get-Content src/shared/infra/database/outbox.py -TotalCount 240` | 0 |
| `Get-Content src/shared/infra/database/inbox.py -TotalCount 240` | 0 |
| `Select-String "class .*(OutboxEventModel|InboxEventModel)" src/modules` | 0 |

**Files changed:**
- `src/shared/infra/database/outbox.py` — adicionados routing_key, idempotency_key, locked_at, locked_by, metadata_ ao abstract OutboxEventModel
- `src/shared/infra/database/inbox.py` — adicionados message_id, producer_module, consumer_module, routing_key, headers, idempotency_key, locked_at, locked_by ao abstract InboxEventModel
- `src/modules/billing/infra/database/models.py` — OutboxEventModel/InboxEventModel com constraints canônicas
- `src/modules/core/infra/database/models.py` — OutboxEventModel/InboxEventModel com constraints canônicas
- `src/modules/identity/infra/database/models.py` — OutboxEventModel/InboxEventModel com constraints canônicas
- `src/modules/metering/infra/database/models.py` — OutboxEventModel/InboxEventModel com constraints canônicas
- `src/modules/observability/infra/database/models.py` — OutboxEventModel/InboxEventModel com constraints canônicas
- `migrations/versions/0024_standardize_outbox_inbox_fields.py` — migration append-only com server_default backfill
- `tests/migrations/test_0024_outbox_inbox_standardization.py` — 32 testes de estrutura, constraints, downgrade, duplicatas, locks, transições

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- OutboxEventModel canônico: routing_key, idempotency_key, locked_at, locked_by, metadata_
- InboxEventModel canônico: message_id, producer_module, consumer_module, routing_key, headers, idempotency_key, locked_at, locked_by
- UniqueConstraint(idempotency_key) em outbox de cada módulo
- UniqueConstraint(message_id) + UniqueConstraint(idempotency_key) em inbox de cada módulo
- Partial indexes pending/retryable, correlation_id, aggregate em cada módulo
- Agent mantém seus modelos próprios (já canônicos) sem alteração

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/shared/infra/database/ ...` | 0 |
| `pytest tests/migrations/test_0024_outbox_inbox_standardization.py -v` | 0 (32 passed) |
| `alembic upgrade head` | skipped (no database) |
| `alembic downgrade -1` | skipped (no database) |

**Migration validation:** Alembic requer PostgreSQL — não disponível neste ambiente. Migration validada estaticamente por testes. Aplicar com `alembic upgrade head` antes da próxima spec que requer banco atualizado.

**Riscos:**
- Migration não testada em banco real — validar em staging antes de produção
- Agent continua com modelos próprios (não herdados do shared base) — possível inconsistência futura se shared base evoluir separadamente

## Próxima spec

`006-fix-worker-lifecycle-and-rabbitmq-topology.md`
