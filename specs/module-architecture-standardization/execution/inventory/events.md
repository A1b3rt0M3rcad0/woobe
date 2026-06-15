# Event / Outbox / Inbox Catalog

**Date:** 2026-06-14
**Branch:** project-rai-playground_module-architecture-standardization
**SHA:** d12e2b6

## Notes
- Generated during spec 016 execution.
- `rg` unavailable on Windows; substituted with `Select-String -Pattern 'event_type|routing_key|Outbox|Inbox'`.
- Detection scope: `src/modules` and `migrations`.

## Shared Event Infrastructure

### OutboxEventWriter (abstract contract)
| File | Description |
|---|---|
| `src/shared/domain/events.py` | Abstract `OutboxEventWriter` with `write(aggregate_type, aggregate_id, event_type, payload, ...)` |

### InboxEventModel (abstract base class)
| File | Description |
|---|---|
| `src/shared/infra/database/inbox.py` | Abstract `InboxEventModel` with fields: `outbox_origin_id`, `aggregate_type`, `event_type`, `event_version`, `payload`, `status`, `attempts`, `available_at`, `processed_at`, `error`, `consumer_name`, `correlation_id`, `causation_id` |

## Agent Module Events

### Domain Event Classes
| Class | File | event_type | routing_key | Versioned? |
|---|---|---|---|---|
| `AgentDomainEvent` (base) | `src/modules/agent/domain/events.py` | (required) | (required) | No (base) |
| `AgentExecutionRequestedV1` | `src/modules/agent/domain/events.py` | `agent.execution.requested.v1` | `agent.execution.requested.v1` | Yes |
| `AgentExecutionCompletedV1` | `src/modules/agent/domain/events.py` | `agent.execution.completed.v1` | `agent.execution.completed.v1` | Yes |
| `AgentExecutionFailedV1` | `src/modules/agent/domain/events.py` | `agent.execution.failed.v1` | `agent.execution.failed.v1` | Yes |
| `AgentKnowledgeDocumentIndexedV1` | `src/modules/agent/domain/events.py` | `agent.knowledge.document_indexed.v1` | `agent.knowledge.document_indexed.v1` | Yes |
| `AgentFallbackTriggeredV1` | `src/modules/agent/domain/events.py` | `agent.execution.fallback_triggered.v1` | `agent.execution.fallback_triggered.v1` | Yes |

### Legacy event_type strings used in agent use_cases
| event_type | Source File | Legacy? |
|---|---|---|
| `runtime.session.created` | `agent/application/use_cases/runtime_use_cases.py` | Yes (runtime namespace) |
| `runtime.ask.completed` | `agent/application/use_cases/runtime_use_cases.py`, `ask_use_case.py`, `ask_agent_stream_service.py` | Yes |
| `knowledge.collection.created` | `agent/application/use_cases/knowledge_use_cases.py` | Yes (knowledge namespace) |
| `knowledge.document.uploaded` | `agent/application/use_cases/knowledge_use_cases.py` | Yes |
| `usage_event.recorded` | `agent/application/use_cases/ask_use_case.py`, `ask_agent_stream_service.py` | No (metering owned) |
| `provider_credential.created` | `agent/application/use_cases/ai_use_cases.py` | Yes (ai namespace) |
| `provider_credential.updated` | `agent/application/use_cases/ai_use_cases.py` | Yes |
| `agent.created` | `agent/application/use_cases/ai_use_cases.py` | Yes (ai namespace) |
| `agent.updated` | `agent/application/use_cases/ai_use_cases.py` | Yes |

### Agent Messaging Infrastructure
| Component | File |
|---|---|
| `AgentInboxEventRouter` | `src/modules/agent/infra/messaging/inbox_handlers.py` |
| `AgentRabbitMQPublisher` | `src/modules/agent/infra/messaging/publishers.py` |
| Event mappers | `src/modules/agent/infra/messaging/event_mappers.py` |
| `AgentInboxConsumerWorker` | `src/modules/agent/infra/workers/inbox_consumer.py` |
| `AgentInboxProcessorWorker` | `src/modules/agent/infra/workers/inbox_processor.py` |
| `AgentOutboxDispatcherWorker` | `src/modules/agent/infra/workers/outbox_dispatcher.py` |
| `AgentWorkerRegistry` | `src/modules/agent/infra/workers/registry.py` |

### Agent Outbox/Inbox Writers
| Writer Class | File |
|---|---|
| `SQLAlchemyOutboxEventWriter` | `src/modules/agent/infra/database/repositories.py` (line 252) |
| `SQLAlchemyKnowledgeOutboxEventWriter` | `src/modules/agent/infra/database/repositories.py` (line 1003) |
| `SQLAlchemyRuntimeOutboxEventWriter` | `src/modules/agent/infra/database/repositories.py` (line 1207) |

### Agent Outbox/Inbox Models
| Model | Base | File |
|---|---|---|
| `AgentOutboxEventModel` | custom schema | `src/modules/agent/infra/database/models.py` |
| `AgentInboxEventModel` | custom schema | `src/modules/agent/infra/database/models.py` |
| `OutboxEventModel` | `BaseOutbox` | `src/modules/agent/infra/database/models.py` |
| `InboxEventModel` | `BaseInbox` | `src/modules/agent/infra/database/models.py` |
| `KnowledgeOutboxEventModel` | `BaseOutbox` | `src/modules/agent/infra/database/models.py` |
| `KnowledgeInboxEventModel` | `BaseInbox` | `src/modules/agent/infra/database/models.py` |
| `RuntimeOutboxEventModel` | `BaseOutbox` | `src/modules/agent/infra/database/models.py` |
| `RuntimeInboxEventModel` | `BaseInbox` | `src/modules/agent/infra/database/models.py` |

## Other Modules — OutboxEventWriter Implementations

| Module | Writer Class | File |
|---|---|---|
| billing | `SQLAlchemyOutboxEventWriter` | `src/modules/billing/infra/repositories.py` |
| core | `SQLAlchemyOutboxEventWriter` | `src/modules/core/infra/repositories.py` |
| identity | `SQLAlchemyOutboxEventWriter` | `src/modules/identity/infra/repositories.py` |
| metering | `SQLAlchemyOutboxEventWriter` | `src/modules/metering/infra/repositories.py` |
| observability | `SQLAlchemyOutboxEventWriter` | `src/modules/observability/infra/repositories.py` |
| tools | `SQLAlchemyOutboxEventWriter` | `src/modules/tools/infra/repositories.py` |

### event_type strings used by each module's use cases
| Module | event_type | Source 
|---|---|---|
| billing | `plan.created` | `billing/service/use_cases.py` |
| billing | `customer.created` | `billing/service/use_cases.py` |
| billing | `subscription.created` | `billing/service/use_cases.py` |
| billing | `payment_event.{event_type}` | `billing/service/use_cases.py` |
| core | `project.created` | `core/service/use_cases.py` |
| core | `api_key.created` | `core/service/use_cases.py` |
| core | `project.updated` | `core/service/use_cases.py` |
| identity | `user.created` | `identity/service/use_cases.py` |
| identity | `organization.created` | `identity/service/use_cases.py` |
| identity | `organization.member_added` | `identity/service/use_cases.py` |
| identity | `organization.updated` | `identity/service/use_cases.py` |
| identity | `organization.invite_created` | `identity/service/use_cases.py` |
| metering | `usage_event.recorded` | `metering/service/use_cases.py` |
| observability | `trace.created` | `observability/service/use_cases.py` |
| observability | `trace_event.created` | `observability/service/use_cases.py` |
| tools | `tools.tool.created` | `tools/service/use_cases.py` |
| tools | `tools.secret.created` | `tools/service/use_cases.py` |
| tools | `tools.tool.updated` | `tools/service/use_cases.py` |
| tools | `tools.tool.status_changed` | `tools/service/use_cases.py` |

### Outbox/Inbox Models per module
| Module | OutboxEventModel | InboxEventModel | File |
|---|---|---|---|
| billing | `OutboxEventModel(BaseOutbox)` | `InboxEventModel(BaseInbox)` | `src/modules/billing/infra/models.py` |
| core | `OutboxEventModel(BaseOutbox)` | `InboxEventModel(BaseInbox)` | `src/modules/core/infra/models.py` |
| identity | `OutboxEventModel(BaseOutbox)` | `InboxEventModel(BaseInbox)` | `src/modules/identity/infra/models.py` |
| metering | `OutboxEventModel(BaseOutbox)` | `InboxEventModel(BaseInbox)` | `src/modules/metering/infra/models.py` |
| observability | `OutboxEventModel(BaseOutbox)` | `InboxEventModel(BaseInbox)` | `src/modules/observability/infra/models.py` |
| tools | `OutboxEventModel(BaseOutbox)` | `InboxEventModel(BaseInbox)` | `src/modules/tools/infra/models.py` |

### Additional Event Models per module
| Module | Model | File |
|---|---|---|
| billing | `PaymentEventModel` | `src/modules/billing/infra/models.py` |
| billing | `SQLAlchemyPaymentEventRepository` | `src/modules/billing/infra/repositories.py` |
| metering | `UsageEventModel` | `src/modules/metering/infra/models.py` |
| metering | `SQLAlchemyUsageEventRepository` | `src/modules/metering/infra/repositories.py` |
| observability | `TraceEventModel` | `src/modules/observability/infra/models.py` |
| observability | `SQLAlchemyTraceEventRepository` | `src/modules/observability/infra/repositories.py` |

### Domain event enums
| Module | Enum | Values | File |
|---|---|---|---|
| metering | `UsageEventType` | `llm_request`, `llm_response`, ... | `src/modules/metering/domain/enums.py` |
| observability | `TraceEventType` | `info`, `warning`, `error`, `debug` | `src/modules/observability/domain/enums.py` |

## Migration Files Related to Events
| Migration | Purpose | File |
|---|---|---|
| `0002_create_all_tables` | Creates base `outbox_events` table | `migrations/versions/0002_create_all_tables.py` |
| `0005_fix_datetime_timezones` | Fixes timezone on OUTBOX_COLUMNS | `migrations/versions/0005_fix_datetime_timezones.py` |
| `0013_create_agent_outbox_events` | Creates agent-specific outbox events table | `migrations/versions/0013_create_agent_outbox_events.py` |
| `0014_create_agent_inbox_events` | Creates agent-specific inbox events table | `migrations/versions/0014_create_agent_inbox_events.py` |

## Event Naming Convention Analysis

| Convention | Modules Following | Modules Not Following |
|---|---|---|
| `{module}.{event}.v{version}` (versioned) | agent | billing, core, identity, metering, observability, tools |
| `{module}.{action}.{noun}` (unversioned) | billing, core, identity, metering, observability | — |
| Legacy `{legacy_namespace}.{event}` | agent (ai/knowledge/runtime) | — |

## Gaps and Risks

| Gap/Risk | Command needed | Severity |
|---|---|---|
| Only agent uses versioned event naming (`agent.*.v1`) | Standardize envelopes (spec 090) | high |
| 6 modules use unversioned event_type strings | Migrate to versioned (spec 090) | high |
| Agent has 3 separate OutboxEventWriter implementations (base, knowledge, runtime) | Consolidate (spec 026) | medium |
| Agent has 3 separate outbox/inbox model pairs (base, knowledge, runtime) | Consolidate (spec 026) | medium |
| Legacy event namespaces (ai/, knowledge/, runtime/) still in agent use_cases | Migrate to agent namespace (spec 029) | high |
| No common event envelope contract across modules | Define shared EventEnvelope (spec 090) | high |
| `BaseOutbox`/`BaseInbox` abstract models in shared are used inconsistently (agent has custom + base models) | Standardize (spec 090-092) | medium |
| `AgentInboxEventRouter` is agent-only; other modules have no inbox routing | Create per-module routers (spec 037-087) | high |
| Only agent has `AgentRabbitMQPublisher`; others write to outbox but have no publisher | Create per-module publishers (spec 037-087) | high |
| No dead-letter or retry-with-backoff policy found | Standardize retry (spec 094) | medium |

## Structured Command Output

Command: `Select-String -Pattern 'event_type|routing_key|Outbox|Inbox' src/modules migrations -Filter *.py`

Result: ~65 unique files matched. Full catalog above.

## Acceptance Criteria

- [x] `events.md` exists and is not empty
- [x] SHA of inventory registered: `d12e2b6`
- [x] Gaps have explicit commands and risks
- [x] Event types catalogued per module
- [x] Outbox/Inbox models catalogued per module
- [x] Messaging infrastructure (publishers, routers, workers) catalogued
- [x] Naming convention analysis included
