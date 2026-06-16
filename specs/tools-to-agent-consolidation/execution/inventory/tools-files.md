# Tools File Inventory

Total `.py` files: 58 (excluding `__pycache__`)

## Layer: `domain/`

| File | Responsibility | Action |
|---|---|---|
| `__init__.py` | Package init | keep |
| `entities.py` | Tool, Secret dataclass entities | move to `agent.domain` |
| `enums.py` | ToolType, RiskLevel, SecretType, ToolStatus | move to `agent.domain` |
| `errors.py` | ToolNotFoundError, SecretNotFoundError, DuplicateSecretError | move to `agent.domain` |
| `events.py` | (empty, `from __future__ import annotations` only) | merge as needed |
| `repositories.py` | ToolRepository, SecretRepository ABCs | move to `agent.domain` |
| `services.py` | (empty) | merge as needed |
| `value_objects.py` | (empty) | merge as needed |

## Layer: `application/`

| File | Responsibility | Action |
|---|---|---|
| `__init__.py` | Package init | keep |
| `tool_converter.py` | Tool conversion utilities | move to `agent.application` |
| `dtos/__init__.py` | Package init | keep |
| `dtos/tools_dtos.py` | 11 DTOs (CreateToolInput, CreateToolOutput, etc.) | move to `agent.application.dtos` |
| `use_cases/__init__.py` | Package init | keep |
| `use_cases/tools_use_cases.py` | 8 use cases (CRUD + execute + test + list) | move to `agent.application.use_cases` |
| `composers/__init__.py` | Package init | keep |
| `composers/create_secret_composer.py` | DI composition for create secret | move to `agent.application.composers` |
| `composers/create_tool_composer.py` | DI composition for create tool | move to `agent.application.composers` |
| `composers/delete_tool_composer.py` | DI composition for delete tool | move to `agent.application.composers` |
| `composers/execute_tool_composer.py` | DI composition for execute tool | move to `agent.application.composers` |
| `composers/list_secrets_composer.py` | DI composition for list secrets | move to `agent.application.composers` |
| `composers/list_tools_by_agent_composer.py` | DI composition for list tools by agent | move to `agent.application.composers` |
| `composers/list_tools_composer.py` | DI composition for list tools | move to `agent.application.composers` |
| `composers/test_tool_composer.py` | DI composition for test tool | move to `agent.application.composers` |
| `composers/update_tool_composer.py` | DI composition for update tool | move to `agent.application.composers` |
| `composers/update_tool_status_composer.py` | DI composition for update tool status | move to `agent.application.composers` |
| `handlers/__init__.py` | (empty) | merge as needed |

## Layer: `infra/database/`

| File | Responsibility | Action |
|---|---|---|
| `__init__.py` | Package init | keep |
| `models.py` | ToolModel, SecretModel, OutboxEventModel, InboxEventModel (schema: tools) | move to `agent.infra.database` |
| `mappers.py` | ORM <-> domain mappers (4 functions) | move to `agent.infra.database` |
| `repositories.py` | SQLAlchemyToolRepository, SQLAlchemySecretRepository, SQLAlchemyOutboxEventWriter | move to `agent.infra.database` |
| `unit_of_work.py` | ToolsUnitOfWork (own UoW in tools schema) | merge into AgentUnitOfWork |

## Layer: `infra/messaging/`

| File | Responsibility | Action |
|---|---|---|
| `__init__.py` | Package init | keep |
| `consumers.py` | ToolsRabbitMQConsumer (generic Rabbit consumer wrapper) | merge into agent messaging |
| `event_mappers.py` | outbox_to_rabbit_message, rabbit_message_to_inbox, RabbitMQMessageEnvelope | move to `agent.infra.messaging` |
| `inbox_handlers.py` | ToolsInboxEventRouter with HANDLED_EVENTS dict | merge into agent inbox handlers |
| `publishers.py` | ToolsRabbitMQPublisher (publish to RabbitMQ) | merge into agent messaging |

## Layer: `infra/workers/`

| File | Responsibility | Action |
|---|---|---|
| `__init__.py` | Package init | keep |
| `inbox_consumer.py` | ToolsInboxConsumerWorker (polls InboxEventModel in tools schema) | move to `agent.infra.workers` |
| `inbox_processor.py` | ToolsInboxProcessorWorker (Rabbit -> InboxEventModel) | move to `agent.infra.workers` |
| `outbox_dispatcher.py` | ToolsOutboxDispatcherWorker (polls OutboxEventModel in tools schema) | move to `agent.infra.workers` |
| `registry.py` | ToolsWorkerRegistry (currently empty: `register_tools_workers()` is a no-op) | merge into agent worker registry |

## Layer: `presentation/`

| File | Responsibility | Action |
|---|---|---|
| `__init__.py` | Package init | keep |
| `routes.py` | 10 routes under prefix `/tools`, `/agents/{agent_id}/tools`, `/secrets` | move/shim to `agent.presentation` |
| `schemas.py` | 9 request/response Pydantic schemas | move to `agent.presentation` |
| `mappers.py` | Presentation mappers | move to `agent.presentation` |
| `controllers/__init__.py` | Package init | keep |
| `controllers/create_secret_controller.py` | Controller for create secret | move to `agent.presentation.controllers` |
| `controllers/create_tool_controller.py` | Controller for create tool | move to `agent.presentation.controllers` |
| `controllers/delete_tool_controller.py` | Controller for delete tool | move to `agent.presentation.controllers` |
| `controllers/execute_tool_controller.py` | Controller for execute tool | move to `agent.presentation.controllers` |
| `controllers/list_secrets_controller.py` | Controller for list secrets | move to `agent.presentation.controllers` |
| `controllers/list_tools_by_agent_controller.py` | Controller for list tools by agent | move to `agent.presentation.controllers` |
| `controllers/list_tools_controller.py` | Controller for list tools | move to `agent.presentation.controllers` |
| `controllers/test_tool_controller.py` | Controller for test tool | move to `agent.presentation.controllers` |
| `controllers/update_tool_controller.py` | Controller for update tool | move to `agent.presentation.controllers` |
| `controllers/update_tool_status_controller.py` | Controller for update tool status | move to `agent.presentation.controllers` |

## Classification summary

- **move**: 46 files (domain, application, infra/database, infra/messaging, presentation)
- **merge**: 8 files (UoW, inbox handlers, publishers, consumers, worker registry)
- **keep**: 6 `__init__.py` files as package markers
- **rewrite**: 0
- **shim**: routes.py will need compatibility shim during cutover
- **delete**: 0 (entire module removed in spec 016)

Executed: `Get-ChildItem -Path src/modules/tools -Recurse -File -Filter "*.py" | Sort-Object FullName`
Exit code: 0
