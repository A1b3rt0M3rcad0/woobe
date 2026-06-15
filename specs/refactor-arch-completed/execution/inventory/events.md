# Event Catalog — Current State

Generated: 2026-06-13
Spec: 007-create-current-event-catalog
Commands executed: `grep event_type= src`, `grep OutboxEvent|InboxEvent src`, `grep register_handler|routing_key|queue_name src`

## Infrastructure

### RabbitMQ

| Component | Location | Detail |
|---|---|---|
| RabbitMQManager | `src/shared/infra/rabbitmq.py:6` | Exchange type: TOPIC, durable. Exchange name configured via `rabbitmq_exchange` setting. |
| Default exchange name | `src/shared/infra/config/config.py:21` | `projectrai.events` |
| Publish method | `src/shared/infra/rabbitmq.py:36` | `routing_key` = event_type; message is PERSISTENT, content_type JSON |
| Consume method | `src/shared/infra/rabbitmq.py:45` | Binds queue to exchange with provided routing_keys |

### Outbox base model

| Field | Type | Location |
|---|---|---|
| aggregate_type | String(128) | `src/shared/infra/database/outbox.py:16` |
| aggregate_id | UUID | `src/shared/infra/database/outbox.py:17` |
| event_type | String(255) | `src/shared/infra/database/outbox.py:18` |
| event_version | Integer (default 1) | `src/shared/infra/database/outbox.py:19` |
| payload | JSONB | `src/shared/infra/database/outbox.py:20` |
| status | String(32) (default "pending") | `src/shared/infra/database/outbox.py:21` |
| attempts | Integer (default 0) | `src/shared/infra/database/outbox.py:22` |
| available_at | DateTime(tz) | `src/shared/infra/database/outbox.py:23` |
| published_at | DateTime(tz) nullable | `src/shared/infra/database/outbox.py:28` |
| error | Text nullable | `src/shared/infra/database/outbox.py:29` |
| correlation_id | UUID nullable | `src/shared/infra/database/outbox.py:30` |
| causation_id | UUID nullable | `src/shared/infra/database/outbox.py:31` |

### Inbox base model

| Field | Type | Location |
|---|---|---|
| outbox_origin_id | UUID nullable | `src/shared/infra/database/inbox.py:16` |
| aggregate_type | String(128) | `src/shared/infra/database/inbox.py:17` |
| event_type | String(255) | `src/shared/infra/database/inbox.py:18` |
| event_version | Integer (default 1) | `src/shared/infra/database/inbox.py:19` |
| payload | JSONB | `src/shared/infra/database/inbox.py:20` |
| status | String(32) (default "pending") | `src/shared/infra/database/inbox.py:21` |
| attempts | Integer (default 0) | `src/shared/infra/database/inbox.py:22` |
| available_at | DateTime(tz) | `src/shared/infra/database/inbox.py:23` |
| processed_at | DateTime(tz) nullable | `src/shared/infra/database/inbox.py:28` |
| error | Text nullable | `src/shared/infra/database/inbox.py:29` |
| consumer_name | String(128) nullable | `src/shared/infra/database/inbox.py:30` |
| correlation_id | UUID nullable | `src/shared/infra/database/inbox.py:31` |
| causation_id | UUID nullable | `src/shared/infra/database/inbox.py:32` |

### OutboxEventWriter contract

| Location | Signature |
|---|---|
| `src/shared/domain/events.py:6` | `write(aggregate_type, aggregate_id, event_type, payload, event_version=1, correlation_id=None, causation_id=None)` |

## Outbox/Inbox tables per module

| Module | Schema | Outbox table | Inbox table | Location |
|---|---|---|---|---|
| identity | identity | identity.outbox_events | identity.inbox_events | `src/modules/identity/infra/models.py:94-100` |
| core | core | core.outbox_events | core.inbox_events | `src/modules/core/infra/models.py:55-61` |
| ai | ai | ai.outbox_events | ai.inbox_events | `src/modules/ai/infra/models.py:67-73` |
| knowledge | knowledge | knowledge.outbox_events | knowledge.inbox_events | `src/modules/knowledge/infra/models.py:93-99` |
| runtime | runtime | runtime.outbox_events | runtime.inbox_events | `src/modules/runtime/infra/models.py:64-71` |
| tools | tools | tools.outbox_events | tools.inbox_events | `src/modules/tools/infra/models.py:45-52` |
| metering | metering | metering.outbox_events | metering.inbox_events | `src/modules/metering/infra/models.py:65-72` |
| billing | billing | billing.outbox_events | billing.inbox_events | `src/modules/billing/infra/models.py:76-83` |
| observability | observability | observability.outbox_events | observability.inbox_events | `src/modules/observability/infra/models.py:53-59` |

## Workers

### OutboxPublisherWorker

| Property | Value | Location |
|---|---|---|
| File | `src/shared/workers/outbox_publisher.py:10` | |
| MODULES list | identity, core, ai, knowledge, runtime, tools, metering, billing, observability | Line 12-15 |
| MAX_ATTEMPTS | 5 | Line 16 |
| BATCH_SIZE | 50 | Line 17 |
| Routing key | `event.event_type` (uses event_type as RabbitMQ routing key) | Line 46 |
| Published envelope | id, aggregate_type, aggregate_id, event_type, event_version, payload, correlation_id, causation_id | Lines 47-56 |
| Status transitions | pending → published (success), pending → failed (error, attempts < 5), pending → dead (attempts >= 5) | Lines 63-67 |

### InboxConsumerWorker

| Property | Value | Location |
|---|---|---|
| File | `src/shared/workers/inbox_consumer.py:14` | |
| Queue name | `projectrai.inbox` (single global queue) | Line 16 |
| Routing keys | `["#"]` (subscribes to ALL events) | Line 24 |
| Module routing | `event_type.split(".", 1)[0]` — first segment of event_type determines target module | Line 10-11 |
| Dynamic import | `importlib.import_module(f"modules.{module}.infra.models")` | Line 37 |
| Failure mode | If module import fails, silently returns without persisting to inbox | Lines 39-40 |

### InboxDispatcherWorker

| Property | Value | Location |
|---|---|---|
| File | `src/shared/workers/inbox_dispatcher.py:12` | |
| MODULES list | identity, core, ai, knowledge, runtime, tools, metering, billing, observability | Lines 14-17 |
| MAX_ATTEMPTS | 5 | Line 18 |
| BATCH_SIZE | 50 | Line 19 |
| Handler registry | `dict[str, EventHandler]` keyed by event_type string | Line 24 |
| Status transitions | pending → processed (success), pending → failed (error, attempts < 5), pending → dead (attempts >= 5) | Lines 57-62 |

### Dispatcher (handler registration)

| Handler event_type key | Handler function | Location |
|---|---|---|
| `identity.organization_created` | handle_organization_created | `src/workers/dispatcher.py:35` |
| `core.project_created` | handle_project_created | `src/workers/dispatcher.py:36` |
| `ai.agent_created` | handle_agent_created | `src/workers/dispatcher.py:37` |
| `knowledge.document.uploaded` | handle_document_uploaded | `src/workers/dispatcher.py:38` |
| `metering.usage_recorded` | handle_usage_recorded | `src/workers/dispatcher.py:39` |

All handler implementations are stubs (log-only TODOs) at `src/workers/dispatcher.py:8-29`.

## Event catalog by module

### Module: identity

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `user.created` | user | CreateUserUseCase | `src/modules/identity/service/use_cases.py:78` | email |
| `user.created` | user | RegisterUseCase | `src/modules/identity/service/use_cases.py:342` | email |
| `organization.created` | organization | CreateOrganizationUseCase | `src/modules/identity/service/use_cases.py:113` | name, slug |
| `organization.created` | organization | RegisterUseCase | `src/modules/identity/service/use_cases.py:355` | name, slug |
| `organization.member_added` | organization_member | AddMemberToOrganizationUseCase | `src/modules/identity/service/use_cases.py:166` | user_id, organization_id, role |
| `organization.member_added` | organization_member | RegisterUseCase | `src/modules/identity/service/use_cases.py:370` | user_id, organization_id, role |
| `organization.updated` | organization | UpdateOrganizationUseCase | `src/modules/identity/service/use_cases.py:216` | name, slug |
| `organization.invite_created` | organization_invite | InviteUserUseCase | `src/modules/identity/service/use_cases.py:267` | organization_id, email, role |

### Module: core

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `project.created` | project | CreateProjectUseCase | `src/modules/core/service/use_cases.py:54` | organization_id, name, slug |
| `api_key.created` | api_key | CreateApiKeyUseCase | `src/modules/core/service/use_cases.py:107` | project_id, name |
| `project.updated` | project | UpdateProjectUseCase | `src/modules/core/service/use_cases.py:188` | name, slug |

### Module: ai

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `provider_credential.created` | provider_credential | CreateProviderCredentialUseCase | `src/modules/ai/service/use_cases.py:95` | project_id, provider, name |
| `provider_credential.updated` | provider_credential | UpdateProviderCredentialUseCase | `src/modules/ai/service/use_cases.py:146` | project_id, provider, name |
| `agent.created` | agent | CreateAgentUseCase | `src/modules/ai/service/use_cases.py:209` | project_id, name, provider, model |
| `agent.updated` | agent | UpdateAgentUseCase | `src/modules/ai/service/use_cases.py:254` | project_id, name, provider, model |

### Module: knowledge

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `knowledge.collection.created` | document_collection | CreateCollectionUseCase | `src/modules/knowledge/service/use_cases.py:121` | collection_id, project_id, name |
| `knowledge.document.uploaded` | document | UploadDocumentUseCase | `src/modules/knowledge/service/use_cases.py:171` | document_id, collection_id, project_id, file_name, storage_key, parser |

### Module: runtime

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `runtime.session.created` | session | CreateSessionUseCase | `src/modules/runtime/service/use_cases.py:48` | session_id, project_id, agent_id, mode |
| `runtime.ask.completed` | message | SendMessageUseCase | `src/modules/runtime/service/use_cases.py:104` | message_id, session_id, project_id, agent_id, role |
| `runtime.ask.completed` | message | AskAgentUseCase | `src/modules/runtime/service/ask_use_case.py:578` | message_id, session_id, project_id, agent_id, role |
| `runtime.ask.completed` | message | AskAgentStreamService | `src/modules/runtime/service/ask_agent_stream_service.py:749` | message_id, session_id, project_id, agent_id, role |

### Module: tools

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `tools.tool.created` | tool | CreateToolUseCase | `src/modules/tools/service/use_cases.py:64` | tool_id, project_id, agent_id, name, type, risk_level |
| `tools.secret.created` | secret | CreateSecretUseCase | `src/modules/tools/service/use_cases.py:120` | secret_id, project_id, name, type |
| `tools.tool.updated` | tool | UpdateToolUseCase | `src/modules/tools/service/use_cases.py:175` | tool_id, name |
| `tools.tool.status_changed` | tool | UpdateToolStatusUseCase | `src/modules/tools/service/use_cases.py:214` | tool_id, status |

### Module: billing

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `plan.created` | Plan | CreatePlanUseCase | `src/modules/billing/service/use_cases.py:57` | code, name, price_usd |
| `customer.created` | Customer | CreateCustomerUseCase | `src/modules/billing/service/use_cases.py:91` | organization_id, provider |
| `subscription.created` | Subscription | CreateSubscriptionUseCase | `src/modules/billing/service/use_cases.py:130` | organization_id, plan_id, status |
| `payment_event.{dynamic}` | PaymentEvent | HandlePaymentEventUseCase | `src/modules/billing/service/use_cases.py:179` | provider_event_id, subscription_id |

Note: `payment_event.{input_dto.event_type}` produces dynamic event_type values at runtime (e.g., `payment_event.invoice.payment_succeeded`, `payment_event.subscription.canceled`).

### Module: metering

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `usage_event.recorded` | UsageEvent | RecordUsageUseCase | `src/modules/metering/service/use_cases.py:43` | project_id, agent_id, event_type, quantity, unit |

### Module: observability

| event_type | aggregate_type | Producer | Location | Payload fields |
|---|---|---|---|---|
| `trace.created` | Trace | CreateTraceUseCase | `src/modules/observability/service/use_cases.py:57` | project_id, status, provider |
| `trace_event.created` | TraceEvent | CreateTraceEventUseCase | `src/modules/observability/service/use_cases.py:95` | trace_id, event_type |

## Cross-module event production (violations)

| Source module | event_type produced | Target domain | Location | Issue |
|---|---|---|---|---|
| runtime | `usage_event.recorded` | metering | `src/modules/runtime/service/ask_use_case.py:928` | Runtime directly writes metering-domain outbox event via its own outbox; should publish own event and let metering consume |
| runtime | `usage_event.recorded` | metering | `src/modules/runtime/service/ask_agent_stream_service.py:1062` | Same violation as above, stream variant |

## Naming convention analysis

### Events WITH module prefix (conformant to `<module>.<aggregate_event>.vN` pattern)

| event_type | Module | Conforms |
|---|---|---|
| `knowledge.collection.created` | knowledge | partial (no version suffix) |
| `knowledge.document.uploaded` | knowledge | partial (no version suffix) |
| `runtime.session.created` | runtime | partial (no version suffix) |
| `runtime.ask.completed` | runtime | partial (no version suffix) |
| `tools.tool.created` | tools | partial (no version suffix) |
| `tools.secret.created` | tools | partial (no version suffix) |
| `tools.tool.updated` | tools | partial (no version suffix) |
| `tools.tool.status_changed` | tools | partial (no version suffix) |

### Events WITHOUT module prefix (non-conformant)

| event_type | Actual module | First segment (inbox routing target) | Routing result |
|---|---|---|---|
| `user.created` | identity | `user` | FAILS — no module "user" exists |
| `organization.created` | identity | `organization` | FAILS — no module "organization" exists |
| `organization.member_added` | identity | `organization` | FAILS — no module "organization" exists |
| `organization.updated` | identity | `organization` | FAILS — no module "organization" exists |
| `organization.invite_created` | identity | `organization` | FAILS — no module "organization" exists |
| `project.created` | core | `project` | FAILS — no module "project" exists |
| `api_key.created` | core | `api_key` | FAILS — no module "api_key" exists |
| `project.updated` | core | `project` | FAILS — no module "project" exists |
| `provider_credential.created` | ai | `provider_credential` | FAILS — no module "provider_credential" exists |
| `provider_credential.updated` | ai | `provider_credential` | FAILS — no module "provider_credential" exists |
| `agent.created` | ai | `agent` | FAILS — no module "agent" exists (yet) |
| `agent.updated` | ai | `agent` | FAILS — no module "agent" exists (yet) |
| `plan.created` | billing | `plan` | FAILS — no module "plan" exists |
| `customer.created` | billing | `customer` | FAILS — no module "customer" exists |
| `subscription.created` | billing | `subscription` | FAILS — no module "subscription" exists |
| `payment_event.{dynamic}` | billing | `payment_event` | FAILS — no module "payment_event" exists |
| `usage_event.recorded` | metering | `usage_event` | FAILS — no module "usage_event" exists |
| `trace.created` | observability | `trace` | FAILS — no module "trace" exists |
| `trace_event.created` | observability | `trace_event` | FAILS — no module "trace_event" exists |

### Dispatcher handler keys vs actual event_type mismatch

| Dispatcher key | Expected module source | Actual event_type produced | Match? |
|---|---|---|---|
| `identity.organization_created` | identity | `organization.created` | NO |
| `core.project_created` | core | `project.created` | NO |
| `ai.agent_created` | ai | `agent.created` | NO |
| `knowledge.document.uploaded` | knowledge | `knowledge.document.uploaded` | YES |
| `metering.usage_recorded` | metering | `usage_event.recorded` | NO |

## Event versioning

All events use `event_version=1` (default). No event has an explicit version suffix in its `event_type` string. The `event_version` field exists in both Outbox and Inbox models but is never set to a value other than 1 in any producer.

## Envelope structure (as published to RabbitMQ)

Published by `OutboxPublisherWorker` at `src/shared/workers/outbox_publisher.py:47-56`:

```json
{
  "id": "<outbox_event_uuid>",
  "aggregate_type": "<string>",
  "aggregate_id": "<uuid>",
  "event_type": "<string>",
  "event_version": 1,
  "payload": { ... },
  "correlation_id": "<uuid|null>",
  "causation_id": "<uuid|null>"
}
```

Missing from envelope: `timestamp`, `producer_module`, `idempotency_key`, `schema_version`, `trace_id`.

## Risks identified

| Risk | Severity | Evidence | Impact |
|---|---|---|---|
| InboxConsumer routing broken for 19/27 event types | critical | `_module_for_event_type()` splits on first `.`; events like `user.created` route to non-existent module `user` | Events from identity, core, ai, billing, metering, observability never reach any Inbox |
| Dispatcher handler keys don't match actual event_types | high | Dispatcher registers `identity.organization_created` but actual event is `organization.created` | 4/5 dispatcher handlers can never fire |
| No idempotency_key in envelope or inbox deduplication | high | Inbox has `outbox_origin_id` but no unique constraint visible in base model | Duplicate processing possible if consumer retries |
| Runtime directly produces metering events | high | `ask_use_case.py:928`, `ask_agent_stream_service.py:1062` | Cross-module domain leakage; runtime knows metering internal event semantics |
| Dynamic event_type in billing | medium | `payment_event.{input_dto.event_type}` at billing use_cases.py:179 | Unbounded event_type namespace; difficult to route or catalog statically |
| No version suffix convention enforced | medium | All events use default version 1; no `.v1` in event_type string | Future schema evolution undefined |
| Single global queue `projectrai.inbox` with `#` binding | medium | inbox_consumer.py:16,24 | All events compete in one queue; no per-module isolation; no DLQ |
| Shared workers hard-code module list | medium | outbox_publisher.py:12-15, inbox_dispatcher.py:14-17 | Adding/removing modules requires code change in shared layer |

## Summary

- Total distinct event_types: 27 (including dynamic `payment_event.{type}`)
- Modules producing events: 9 (identity, core, ai, knowledge, runtime, tools, billing, metering, observability)
- Events with correct module prefix: 8 (knowledge: 2, runtime: 2, tools: 4)
- Events with broken inbox routing: 19
- Dispatcher handlers that can never fire: 4 of 5
- Cross-module event production violations: 2 (runtime → metering)
- Event version used: always 1
- Envelope fields missing vs best practice: timestamp, producer_module, idempotency_key, schema_version, trace_id
