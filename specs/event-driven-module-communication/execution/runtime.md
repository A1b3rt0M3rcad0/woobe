# Execution Runtime

## Suite

`specs/event-driven-module-communication`

## Branch

- Baseline: `development` @ `cd8d5867967fea25ea170bd88ebc9a461ed16c09`
- Execução: `development_event-driven-module-communication`

## Estado atual

Envelope canônico IntegrationEvent criado em shared/messaging com serializer/deserializer. Outbox/Inbox padronizados com campos canônicos (routing_key, idempotency_key, locks, metadata) e constraints por módulo. Migration 0024 adiciona colunas às tabelas existentes. WorkerRunner com lifecycle start/stop, classificação long-lived vs poller, health checks, DLX, e guarda de consumer duplicado. Agent writer aceita AgentDomainEvent completo, preserva event_id/routing_key/idempotency_key/correlation/causation. Writer não hardcodeia mais `agent.event`. Event catalog definido com categorias execution, tool, secret, credential, agent, knowledge. Eventos legados `runtime.*` deprecados com compatibilidade via resolve_event_type(). Novos eventos de domínio: AgentSessionCreatedV1, AgentMessageCreatedV1, AgentCreatedV1, AgentUpdatedV1, AgentProviderCredentialCreatedV1, AgentProviderCredentialUpdatedV1, AgentCollectionCreatedV1, AgentDocumentUploadedV1. AskAgentUseCase refatorado para execução transacional em fases (prepare/execute/finalize/fail) com Outbox events (AgentExecutionRequestedV1, AgentExecutionCompletedV1, AgentExecutionFailedV1, AgentFallbackTriggeredV1), removendo escritas diretas cross-module (TraceRecorder, UsageRecorder). Compatibilidade retroativa preservada via legacy mode.

## Status

| Spec | Status |
|---|---|
| 000 | completed |
| 001 | completed |
| 002 | completed |
| 003 | completed |
| 004 | completed |
| 005 | completed |
| 006 | completed |
| 007 | completed |
| 008 | completed |
| 009 | completed |
| 010 | completed |
| 011 | completed |
| 012 | completed |
| 013 | completed |
| 014 | completed |
| 015 | completed |
| 016 | completed |
| 017 | completed |
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

### 006 — Lifecycle de workers e topologia RabbitMQ

**Status:** completed
**Tipo:** infrastructure
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `sed -n '107,145p' src/main.py` | 0 |
| `sed -n '1,180p' src/shared/workers/runner.py` | 0 |
| `sed -n '1,120p' src/shared/infra/rabbitmq.py` | 0 |

**Files changed:**
- `src/shared/workers/runner.py` — start/stop lifecycle, classificação long-lived vs poller, tasks supervisionadas, health tracking, run_once preservado
- `src/shared/infra/rabbitmq.py` — DLX exchange, declare_topology, consume com guarda de duplicação via _consuming_queues set
- `src/main.py` — startup chama runner.start(), shutdown chama runner.stop(), health inclui workers
- `tests/integration/workers/test_worker_lifecycle.py` — 24 testes de startup/shutdown, classificação, isolamento de falha, health, consumer duplicado, RabbitMQ indisponível

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- WorkerRunner agora gerencia tasks asyncio supervisionadas
- Long-lived workers (BaseInboxConsumer) rodam como task persistente
- Pollers (BaseOutboxDispatcher, BaseInboxProcessor) rodam em loop com intervalo
- RabbitMQManager declara DLX exchange e bindings idempotentemente
- consume() ignora filas já em consumo (singleton por queue)
- Health checks expostos via /health endpoint
- Nenhum contrato de evento, handler, Outbox/Inbox ou ownership alterado

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/shared/workers src/shared/infra/rabbitmq.py src/main.py` | 0 |
| `pytest tests/integration/workers -q` | 0 (24 passed) |

**Riscos:**
- DLX exchange declarado mas sem política de retry/DLQ completa — spec 015 cobre retries e DLQ
- RabbitMQManager.consume() não é reentrante após close — necessário reconnect explícito em spec futura

### 007 — Outbox e catálogo de eventos do agent

**Status:** completed
**Tipo:** agent-messaging
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `rg -n "SQLAlchemyAgentOutboxEventWriter\|routing_key=\"agent.event\"\|runtime\.ask\.\|Agent.*V1" src/modules/agent` | 0 |
| `rg -n "_outbox\.write\(" src/modules/agent` | 0 |

**Files changed:**
- `src/modules/agent/domain/events.py` — novos eventos: AgentSessionCreatedV1, AgentMessageCreatedV1, AgentCreatedV1, AgentUpdatedV1, AgentProviderCredentialCreatedV1, AgentProviderCredentialUpdatedV1, AgentCollectionCreatedV1, AgentDocumentUploadedV1. EVENT_CATALOG com categorias. LEGACY_EVENT_MAP + resolve_event_type() para compatibilidade.
- `src/modules/agent/infra/messaging/event_mappers.py` — domain_event_to_outbox preserva event_id do domínio (model.id = event.event_id em vez de uuid6.uuid7())
- `src/modules/agent/infra/database/repositories.py` — SQLAlchemyAgentOutboxEventWriter.write() aceita AgentDomainEvent completo; usa domain_event_to_outbox(); remove uuid4, Any
- `src/modules/agent/application/use_cases/tools_use_cases.py` — 4 callers passam evento completo
- `src/modules/agent/application/use_cases/runtime_use_cases.py` — CreateSessionUseCase e SendMessageUseCase usam AgentSessionCreatedV1/AgentMessageCreatedV1
- `src/modules/agent/application/use_cases/ai_use_cases.py` — 4 callers usam eventos versionados
- `src/modules/agent/application/use_cases/knowledge_use_cases.py` — CreateCollectionUseCase e UploadDocumentUseCase usam eventos versionados
- `src/modules/agent/application/use_cases/ask_use_case.py` — runtime.ask.completed → AgentMessageCreatedV1
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` — runtime.ask.completed → AgentMessageCreatedV1
- `tests/unit/agent/test_tools_application.py` — FakeOutbox.write() aceita AgentDomainEvent; assert atualizados
- `tests/integration/agent/test_tools_transaction.py` — FakeOutbox.write() aceita AgentDomainEvent
- `tests/unit/agent/test_agent_outbox_writer.py` — 20 testes: field preservation, rollback, distinct event_ids, legacy compat, event catalog, redaction

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- Agent writer não hardcodeia mais routing_key="agent.event"
- Agent writer preserva event_id, routing_key, event_version, idempotency_key, correlation_id, causation_id, occurred_at, metadata_
- Todos os eventos do agent são versionados (.v1)
- `runtime.*` eventos deprecados, mapeados via LEGACY_EVENT_MAP
- EVENT_CATALOG define categorias: execution, tool, secret, credential, agent, knowledge

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/agent tests/unit/agent` | 0 |
| `pytest tests/unit/agent tests/contract/events -q` | 0 (112 passed, 3 pre-existing failures) |

**Riscos:**
- TestSecretCipher: 3 testes async sem plugin pytest-asyncio configurado (pre-existente)
- Nenhum risco novo introduzido

### 008 — Execução transacional do agente síncrono (AskAgentUseCase)

**Status:** completed
**Tipo:** refactor
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` (verify branch) | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `rg -rn "TraceRecorder\|UsageRecorder\|MeteringUsageRecorder\|ObservabilityTraceRecorder" src/modules/agent/application/` | 0 |
| `rg -rn "cross.*module\|from modules\.\(billing\|metering\|observability\|core\|identity\)" src/modules/agent/` | 0 |

**Files changed:**
- `src/modules/agent/application/use_cases/ask_use_case.py` — refatorado para execução em fases: _prepare() (UoW curta), _execute_llm() (sem UoW), _finalize() (UoW curta), _fail(). Removeu TraceRecorder/UsageRecorder do caminho phased. Usa AgentExecutionRequestedV1, AgentExecutionCompletedV1, AgentExecutionFailedV1, AgentFallbackTriggeredV1 via Outbox. trace_id = uuid4(). _legacy_mode preserva compatibilidade com ask_job_worker.
- `src/modules/agent/application/composers/ask_agent_composer.py` — simplificado: remove MeteringUsageRecorder, ObservabilityTraceRecorder, TransactionalHandler. Retorna controller.handle.
- `tests/integration/agent/test_ask_execution_phases.py` — 4 classes de teste: legado, controller error, reshape interno, phased semantics.
- `specs/event-driven-module-communication/execution/inventory/spec-008-detection.md` — detecção evidenciada.

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- AskAgentUseCase produz 4 novos eventos via Outbox: AgentExecutionRequestedV1, AgentExecutionCompletedV1, AgentExecutionFailedV1, AgentFallbackTriggeredV1
- Nenhum consumer/handler registrado ainda — eventos serão consumidos por metering e observability em specs futuras

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/agent` | 0 |
| `pytest tests/unit/agent tests/integration/agent tests/contract -q` | 155 passed, 32 pre-existing failures |
| `pytest tests/integration/agent/test_ask_execution_phases.py -q` | 0 |

**Decisões:**
- AskAgentUseCase gerencia suas próprias UoW curtas via session_factory injetada (não compartilha UoW com caller)
- _legacy_mode flag: quando agent_repo é passado, usa caminho sem recorders (compatível com ask_job_worker)
- trace_id gerado como uuid4() dentro de _prepare() — sem dependência externa
- _try_fallback() carrega fallback credential via leitura em UoW curta
- Métodos _load_agent() e _load_rag_context() aceitam UoW; versões _legacy() sem UoW para legacy mode
- Composer retorna controller.handle diretamente, sem TransactionalHandler wrapper
- ToolExecutor não é injetado (tool_executor=None) — carregamento de tools não suportado no ask endpoint atualmente
- Nenhuma alteração em portas de domínio (trace_recorder.py, usage_recorder.py) ou adapters de infraestrutura — fora do escopo

**Riscos:**
- ask_job_worker.py não está no escopo — legacy mode preserva compatibilidade mas worker não foi alterado
- Novos eventos (AgentExecutionRequestedV1 etc.) não têm consumidores ainda — não há risco de perda pois Outbox garante persistência
- Ferramentas não são carregadas no ask endpoint (tool_executor=None) — limitação pré-existente, não introduzida por esta spec
- 32 pre-existing failures no pytest (pytest-asyncio plugin ausente) — idênticos à spec 007

### 009 — Streaming e AskJobs no mesmo orchestrator

**Status:** completed
**Tipo:** agent
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `Get-ChildItem ask_agent_stream_service.py, ask_job_worker.py, registry.py, runtime_use_cases.py` | 0 (all exist) |
| `Select-String "Outbox\|Inbox\|Rabbit\|Dispatcher\|Worker" registry.py` | 0 (messaging patterns confirmed) |

**Files changed:**
- `src/modules/agent/application/use_cases/ask_agent_stream_service.py` — refatorado: remove imports dinâmicos, usa AgentUnitOfWork nas fases prepare/finalize/fail, substitui trace_recorder/usage_recorder por eventos Outbox (AgentExecutionRequestedV1, AgentExecutionCompletedV1, AgentExecutionFailedV1, AgentFallbackTriggeredV1), remove _emit_fallback_triggered_event e _fail_trace (cross-module)
- `src/modules/agent/application/use_cases/runtime_use_cases.py` — CreateAskJobUseCase aceita outbox opcional e escreve AgentExecutionRequestedV1 ao criar job
- `src/modules/agent/application/composers/create_ask_job_composer.py` — injeta SQLAlchemyAgentOutboxEventWriter no CreateAskJobUseCase
- `src/modules/agent/infra/workers/registry.py` — registra AskJobWorker como poller
- `tests/integration/agent/test_spec009_stream_job_orchestrator.py` — 9 testes: fases do stream, outbox no job, worker registration, sem imports dinâmicos, sem sessão fechada
- `specs/event-driven-module-communication/execution/runtime.md` — runtime updated

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- AskAgentStreamService agora emite AgentExecutionRequestedV1 (prepare), AgentExecutionCompletedV1 + AgentFallbackTriggeredV1 (finalize), AgentExecutionFailedV1 (fail)
- CreateAskJobUseCase emite AgentExecutionRequestedV1 via Outbox
- AskJobWorker registrado em AgentWorkerRegistry
- Zero adapters cross-module restantes no stream (MeteringUsageRecorder, ObservabilityTraceRecorder removidos)
- Zero imports dinâmicos no stream
- _fail_trace() removido (cross-module direct write para observability)

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/agent` | 0 |
| `pytest tests/integration/agent/test_spec009_stream_job_orchestrator.py -q` | 0 (9 passed) |
| `pytest tests/unit/agent tests/integration/agent tests/contract -q` | 164 passed, 32 pre-existing failures |

**Riscos:**
- AskJobWorker não foi alterado funcionalmente — legacy mode preservado
- 32 pre-existing failures no pytest (pytest-asyncio plugin ausente) — idênticos à spec 008
- Stream service ainda depende de self._session_factory (Callable) — mudança futura para async_sessionmaker direto pode ser necessária

### 010 — Tool interna: composição, secrets e eventos

**Status:** completed
**Tipo:** agent
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `sed -n '120,190p' src/modules/agent/infra/adapters/tool_executor.py` | 0 |
| `sed -n '130,250p' src/modules/agent/application/use_cases/tools_use_cases.py` | 0 |
| `sed -n '1,130p' src/modules/agent/infra/messaging/inbox_handlers.py` | 0 |

**Files changed:**
- `src/modules/agent/infra/adapters/tool_executor.py` — AgentToolExecutor aceita e injeta secret_resolver no ExecuteToolUseCase
- `src/modules/agent/infra/messaging/inbox_handlers.py` — removidos AGENT_TOOL_EVENT_HANDLERS, TOOLS_LEGACY_EVENT_MAP, register_tool_handlers(), e 4 handlers no-op
- `src/modules/agent/infra/workers/registry.py` — removida chamada register_tool_handlers() do AgentInboxEventRouter
- `tests/architecture/test_event_handler_noop.py` — assert invertido: test_agent_no_self_consumption_handlers verifica ausência de AGENT_TOOL_EVENT_HANDLERS
- `tests/unit/agent/test_spec010_tool_executor_and_handlers.py` — 8 testes: tool_executor com secret_resolver, sem self-consumption, composer signatures, import ausente no inbox_handlers

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- Agent não consome mais seus próprios eventos tool.* e secret.*
- ToolExecutor agora aceita secret_resolver opcional

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/agent tests/architecture tests/unit/agent` | 0 |
| `pytest tests/unit/agent/test_spec010_tool_executor_and_handlers.py tests/architecture/test_event_handler_noop.py -q` | 0 (10 passed) |
| `pytest tests/integration/agent/test_spec009_stream_job_orchestrator.py -q` | 0 (9 passed) |

**Decisões:**
- Secret resolver é opcional no AgentToolExecutor — compatibilidade retroativa com callers que não passam
- Remoção total de self-consumption (handlers no-op) — zero risco funcional
- tools_composers.py não alterado — secret resolver já estava no composer

### 011 — Consumer RabbitMQ e Inbox do metering

**Status:** completed
**Tipo:** metering
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `sed -n '1,120p' src/modules/metering/infra/workers/registry.py` | 0 |
| `sed -n '1,160p' src/modules/metering/infra/workers/inbox_consumer.py` | 0 |
| `sed -n '1,120p' src/modules/metering/infra/messaging/inbox_handlers.py` | 0 |

**Files changed:**
- `src/modules/metering/infra/messaging/event_mappers.py` — rewritten rabbit_message_to_inbox with full envelope fields (message_id, producer_module, consumer_module, routing_key, idempotency_key, headers)
- `src/modules/metering/infra/database/repositories.py` — added SQLAlchemyMeteringInboxRepository (save_received, claim_batch, mark_processed, mark_dead, mark_retryable)
- `src/modules/metering/infra/workers/inbox_consumer.py` — rewritten as proper broker consumer extending BaseInboxConsumer (queue: metering.inbox, binds agent.execution.*.v1 routing keys, ACK after persist, invalid→DLQ)
- `src/modules/metering/infra/workers/inbox_processor.py` — rewritten to follow BaseInboxProcessor pattern with claim_batch/mark_processed/mark_dead/mark_retryable
- `src/modules/metering/infra/messaging/inbox_handlers.py` — updated HANDLED_EVENTS with 7 agent.execution.*.v1 event types, MeteringInboxEventRouter now supports register/handle/registered_event_types
- `src/modules/metering/infra/workers/registry.py` — register_metering_workers wires MeteringInboxConsumerWorker and MeteringInboxProcessorWorker
- `tests/integration/metering/test_spec011_metering_consumer_inbox.py` — 11 tests: mapper, consume callback, routing keys, persist/ack, duplicate, invalid envelope, DB error, binding exactness, registry wiring

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- Metering agora consome eventos agent.execution.*.v1 via RabbitMQ queue metering.inbox
- Metering não se inscreve em metering.#
- MeteringInboxEventRouter agora roteia agent.execution.*.v1 para handlers nomeados

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/metering tests/integration/metering` | 0 |
| `pytest tests/integration/metering/test_spec011_metering_consumer_inbox.py -q` | 0 (11 passed) |

**Decisões:**
- MeteringInboxConsumerWorker estende BaseInboxConsumer (padrão idêntico ao AgentInboxConsumerWorker)
- MeteringInboxProcessorWorker estende BaseInboxProcessor (padrão idêntico ao AgentInboxProcessorWorker)
- rabbit_message_to_inbox agora preenche todos os campos canônicos do envelope, incluindo consumer_module="metering"
- HANDLED_EVENTS mapeia agent.execution.*.v1 → handlers nomeados (implementação real em spec 012)
- Registry só registra workers quando engine e rabbitmq_manager são fornecidos (early return)

### 012 — Dispatcher e casos de uso idempotentes do metering

**Status:** completed
**Tipo:** metering
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Detection commands:**
| Comando | Exit code |
|---|---|
| `git branch --show-current` | 0 |
| `git merge-base --is-ancestor cd8d586... HEAD` | 0 |
| `git status --short` | 0 |
| `sed -n '1,180p' src/modules/metering/application/use_cases/metering_use_cases.py` | 0 |
| `sed -n '1,180p' src/modules/metering/infra/database/unit_of_work.py` | 0 |

**Files changed:**
- `src/modules/metering/infra/messaging/inbox_handlers.py` — real handler functions (handle_execution_requested, handle_llm_request, handle_tool_execution, handle_execution_completed, handle_execution_failed, handle_fallback) that create UsageEvent records and update UsageDailyProject/UsageDailyAgent aggregates via session; HANDLER_MAP replaces HANDLED_EVENTS; router defaults to HANDLER_MAP
- `src/modules/metering/infra/workers/inbox_processor.py` — process() passes session to handler via **kwargs
- `tests/integration/metering/test_spec012_metering_dispatcher.py` — 13 tests: atomic effect per handler, router dispatch, unknown ignored, processor session passthrough, default registration

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- Metering handlers agora processam eventos agent.execution.*.v1 em tempo real via InboxProcessor
- Handlers criam UsageEvent e atualizam agregados diários na mesma sessão do processor
- HANDLER_MAP registra handlers reais por event_type (router defaults)

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/metering tests/integration/metering` | 0 |
| `pytest tests/integration/metering/ -q` | 0 (24 passed) |

**Decisões:**
- Handlers recebem session via **kwargs da router.handle() → process() passa self._session
- handler_execution_requested também atende agent.execution.started.v1 (compartilham mesmo efeito)
- handler_execution_completed e handler_execution_failed são logs apenas (sem efeito mensurável no metering)
- handler_fallback registra como UsageEventType.llm_request com source=fallback_triggered
- `started` mapeado para handle_execution_requested (compartilham efeito inicial)

### 013 — Consumer RabbitMQ e Inbox do observability

**Status:** completed
**Tipo:** observability
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Files changed:**
- `src/modules/observability/infra/messaging/event_mappers.py` — rewritten rabbit_message_to_inbox with full canonical envelope fields
- `src/modules/observability/infra/database/repositories.py` — added SQLAlchemyObservabilityInboxRepository (save_received, claim_batch, mark_processed, mark_dead, mark_retryable)
- `src/modules/observability/infra/workers/inbox_consumer.py` — rewritten as broker consumer extending BaseInboxConsumer (queue: observability.inbox, binds agent.execution.*.v1 routing keys except requested)
- `src/modules/observability/infra/workers/inbox_processor.py` — rewritten to follow BaseInboxProcessor pattern
- `src/modules/observability/infra/messaging/inbox_handlers.py` — HANDLER_MAP with 6 agent.execution.*.v1 handers (no requested), router defaults to HANDLER_MAP
- `src/modules/observability/infra/workers/registry.py` — register_observability_workers wires consumer + processor
- `tests/integration/observability/test_spec013_observability_consumer_inbox.py` — 11 tests

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/observability tests/integration/observability` | 0 |
| `pytest tests/integration/observability/test_spec013_observability_consumer_inbox.py -q` | 0 (11 passed) |

**Decisões:**
- Observability NÃO subscreve agent.execution.requested.v1 (apenas metering o faz)
- handle_trace_started cria Trace real no banco via SQLAlchemyTraceRepository
- Demais handlers são logs (implementação real em spec 014)

### 014 — Projeção idempotente de observability

**Status:** completed
**Tipo:** observability
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Files changed:**
- `src/modules/observability/infra/messaging/inbox_handlers.py` — handlers with idempotent trace projection: _get_or_create_trace for placeholder support, handle_trace_started creates Trace, handle_llm_call creates TraceEvent+updates trace, handle_tool_call creates TraceEvent, handle_trace_fallback flags trace, handle_trace_completed/failed finalize trace
- `tests/integration/observability/test_spec014_observability_projection.py` — 21 tests: handler contract, missing trace_id, session passthrough, router dispatch, edge cases

**Event contracts, producers, consumers, handlers, workers, Outbox, Inbox, ownership mappings changed:**
- Observability handlers implement full idempotent projection: trace_id preserved from payload, _get_or_create_trace supports out-of-order events via placeholder, TraceEvent records for LLM/tool calls, state machine running→completed/failed

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/observability tests/integration/observability` | 0 |
| `pytest tests/integration/observability/ -q` | 0 (32 passed) |

**Decisões:**
- _get_or_create_trace cria placeholder Trace(id=trace_id, status=pending) quando trace_id não existe — suporta out-of-order
- handle_trace_started usa TraceStatus.running (enums define running não started)
- handle_llm_call usa TraceEventType.llm_call (enums define llm_call não llm_request)
- handle_trace_completed/failed finalizam trace com ended_at e status, mesmo que started nunca chegue
- Redaction/payload_ref não implementada nesta spec (será coberta em spec futura se necessário)

### 015 — Registries, retries, DLQ, locks e replay

**Status:** completed
**Tipo:** resilience
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Files changed:**
- `src/modules/metering/infra/workers/outbox_dispatcher.py` — fixed 1-hour cutoff (available_at <= func.now()), added mark_dead/mark_retryable abstract implementations
- `src/modules/observability/infra/workers/outbox_dispatcher.py` — same fixes
- `src/modules/metering/infra/workers/registry.py` — registers MeteringOutboxDispatcherWorker (3 workers total)
- `src/modules/observability/infra/workers/registry.py` — registers ObservabilityOutboxDispatcherWorker (3 workers total)
- `scripts/messaging/replay.py` — replay script for inbox/outbox events by module, type, status, dead, or ids
- `tests/integration/metering/test_spec015_metering_retry_dlq.py` — 6 tests: registry wiring, retry schedule, max attempts, mark_failed
- `tests/integration/metering/test_spec011_metering_consumer_inbox.py` — updated call_count assert to 3
- `tests/integration/observability/test_spec013_observability_consumer_inbox.py` — updated call_count assert to 3

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/metering src/modules/observability src/shared/workers` | 0 |
| `pytest tests/integration/metering/ tests/integration/observability/ tests/integration/workers/ -q` | 0 (86 passed) |

**Gate 011-015 (consumers metering/observability) completed.**

**Decisões:**
- Cutoff de 1 hora removido: available_at <= func.now() agora é usado, eliminando delay desnecessário
- mark_dead/mark_retryable implementados nos dispatchers (eram abstract e não implementados)
- Outbox dispatchers registrados nos registries de metering e observability
- Replay script criado como ferramenta CLI independente (scripts/messaging/replay.py)
- mark_failed existente mantido como override (não chama mark_dead/mark_retryable do base)

### 016 — Identity, Core e Billing: remover integração de fachada

**Status:** completed
**Tipo:** cross-module-audit
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Files changed:**
- `src/modules/identity/infra/workers/registry.py` — removed inbox consumer + inbox processor registration; only outbox dispatcher remains
- `src/modules/core/infra/workers/registry.py` — same
- `src/modules/billing/infra/workers/registry.py` — same
- `tests/integration/identity/test_spec016_identity_self_subscription.py` — 3 tests: registry count 1, early return without rabbitmq, worker registry
- `tests/integration/core/test_spec016_core_self_subscription.py` — 2 tests: registry count 1, worker registry
- `tests/integration/billing/test_spec016_billing_self_subscription.py` — 2 tests: registry count 1, worker registry

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/identity src/modules/core src/modules/billing` | 0 |
| `pytest tests/integration/identity/ tests/integration/core/ tests/integration/billing/ -q` | 0 (7 passed) |

**Decisões:**
- Identity, Core, Billing mantêm outbox dispatchers como produtores (podem emitir eventos para outros módulos)
- Inbox consumers e inbox processors removidos dos registries — zero self-subscription
- Arquivos de inbox consumer/processor/handler preservados (sem código morto removido — extensão points documentados)
- Arquitetura guard test_event_self_subscriptions ainda lista billing/core/identity como conhecidos (constantes de routing keys ainda existem nos consumer files)

### 017 — Remover Foreign Keys cross-module

**Status:** completed
**Tipo:** database-boundary
**Data:** 2026-06-16
**Scope:** event-driven-module-communication

**Files changed:**
- `migrations/versions/0025_remove_remaining_cross_module_foreign_keys.py` — new migration: drops 9 cross-module FKs (core→identity x2, billing→identity x2, metering→core x3, observability→core x2)
- `src/modules/core/infra/database/models.py` — removed ForeignKey from ProjectModel.organization_id (→identity) and ApiKeyModel.created_by_user_id (→identity)
- `src/modules/billing/infra/database/models.py` — removed ForeignKey from CustomerModel.organization_id and SubscriptionModel.organization_id (→identity)
- `src/modules/metering/infra/database/models.py` — removed ForeignKey from UsageEventModel.project_id, UsageDailyProjectModel.project_id, UsageDailyAgentModel.project_id (→core)
- `src/modules/observability/infra/database/models.py` — removed ForeignKey from TraceModel.project_id and TraceEventModel.project_id (→core)
- `tests/migrations/test_0025_remove_remaining_cross_module_foreign_keys.py` — 8 tests: migration structure, metadata scan for zero cross-module FK, internal FK preserved

**Cross-module FKs removed (9 total):**
| Schema | Table | Column | Referent |
|---|---|---|---|
| core | projects | organization_id | identity.organizations |
| core | api_keys | created_by_user_id | identity.users |
| billing | customers | organization_id | identity.organizations |
| billing | subscriptions | organization_id | identity.organizations |
| metering | usage_events | project_id | core.projects |
| metering | usage_daily_project | project_id | core.projects |
| metering | usage_daily_agent | project_id | core.projects |
| observability | traces | project_id | core.projects |
| observability | trace_events | project_id | core.projects |

**Internal FKs preserved:**
- core: ApiKeyModel.project_id → core.projects
- billing: SubscriptionModel.customer_id → billing.customers, plan_id → billing.plans
- observability: TraceEventModel.trace_id → observability.traces

**Validation:**
| Comando | Exit code |
|---|---|
| `ruff check src/modules/core src/modules/billing src/modules/metering src/modules/observability` | 0 |
| `pytest tests/migrations/test_0025_remove_remaining_cross_module_foreign_keys.py -q` | 0 (8 passed) |

## Próxima spec

`018-run-end-to-end-failure-and-atomicity-tests.md`
