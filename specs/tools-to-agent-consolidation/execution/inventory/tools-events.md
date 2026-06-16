# Tools Module — Event Inventory

## Produced events (Outbox)

Events written via `OutboxEventWriter` in use cases:

| Event Type | Producer | Payload | When |
|---|---|---|---|
| `tools.tool.created` | `CreateToolUseCase` | tool_id, project_id, agent_id?, name, type, risk_level | Tool created |
| `tools.tool.updated` | `UpdateToolUseCase` | tool_id, name | Tool updated |
| `tools.tool.status_changed` | `UpdateToolStatusUseCase` | tool_id, status | Tool status changed |
| `tools.secret.created` | `CreateSecretUseCase` | secret_id, project_id, name, type | Secret created |

## Consumed events (Inbox)

Handled by `ToolsInboxEventRouter`:

| Event Type | Handler |
|---|---|
| `tools.tool.created` | `handle_tool_created` |
| `tools.tool.updated` | `handle_tool_updated` |
| `tools.tool.status_changed` | `handle_tool_status_changed` |
| `tools.secret.created` | `handle_secret_created` |

**Note:** All 4 handlers are declared in `HANDLED_EVENTS` dict but none have actual implementation logic — current `handle()` method only logs.

## Outbox/Inbox models

| Model | Schema | Table |
|---|---|---|
| `OutboxEventModel` | `tools` | `outbox_events` |
| `InboxEventModel` | `tools` | `inbox_events` |

Both extend shared base models from `shared.infra.database.outbox` / `shared.infra.database.inbox`.

## Messaging infrastructure

| Component | File | Details |
|---|---|---|
| Outbox -> Rabbit mapper | `infra/messaging/event_mappers.py` | Converts OutboxEventModel -> RabbitMQMessageEnvelope |
| Rabbit -> Inbox mapper | `infra/messaging/event_mappers.py` | Converts Rabbit message -> InboxEventModel |
| Publisher | `infra/messaging/publishers.py` | `ToolsRabbitMQPublisher` publishes to RabbitMQ exchange |
| Consumer | `infra/messaging/consumers.py` | `ToolsRabbitMQConsumer` consumes from RabbitMQ queue |
| Outbox dispatcher worker | `infra/workers/outbox_dispatcher.py` | Polls `tools.outbox_events`, publishes via publisher |
| Inbox processor worker | `infra/workers/inbox_processor.py` | Rabbit message -> `tools.inbox_events` |
| Inbox consumer worker | `infra/workers/inbox_consumer.py` | Polls `tools.inbox_events`, routes to handlers |
| Worker registry | `infra/workers/registry.py` | `ToolsWorkerRegistry` (currently `register_tools_workers()` is a no-op) |

## Event envelope type

`tools.tool.created`, `tools.tool.updated`, `tools.tool.status_changed`, `tools.secret.created` follow `module.entity.action` naming convention (pre-standard, does not include version suffix like `v1`).

Executed: `Select-String -Pattern "tools\.(tool|secret)|routing_key|event_type" -Path "src/**/*.py","tests/**/*.py"`
Exit code: 0
