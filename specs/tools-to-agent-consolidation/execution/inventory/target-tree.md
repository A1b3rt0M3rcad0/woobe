# Target Tree — agent module after tools consolidation

```
src/modules/agent/
├── __init__.py
├── application/
│   ├── __init__.py
│   ├── composers/
│   │   ├── __init__.py
│   │   ├── create_tool_composer.py                 # from tools
│   │   ├── update_tool_composer.py                  # from tools
│   │   ├── update_tool_status_composer.py           # from tools
│   │   ├── delete_tool_composer.py                  # from tools
│   │   ├── test_tool_composer.py                    # from tools
│   │   ├── execute_tool_composer.py                 # from tools
│   │   ├── list_tools_composer.py                   # from tools
│   │   ├── list_tools_by_agent_composer.py          # from tools
│   │   ├── create_secret_composer.py                # from tools
│   │   ├── list_secrets_composer.py                 # from tools
│   │   └── ...existing agent composers...
│   ├── dtos/
│   │   ├── __init__.py
│   │   ├── tools_dtos.py                            # from tools (merged)
│   │   └── ...existing agent dtos...
│   ├── handlers/
│   │   └── __init__.py
│   ├── tool_converter.py                            # already exists
│   └── use_cases/
│       ├── __init__.py
│       ├── tools_use_cases.py                       # from tools (merged)
│       └── ...existing agent use cases...
├── domain/
│   ├── __init__.py
│   ├── entities.py                                  # merged: Tool, Secret
│   ├── enums.py                                     # merged: ToolType, RiskLevel, SecretType, ToolStatus
│   ├── errors.py                                    # merged: ToolNotFoundError, SecretNotFoundError, DuplicateSecretError
│   ├── events.py                                    # merged
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── llm_factory.py
│   │   ├── tool_executor.py                         # already exists
│   │   ├── tool_repository.py                       # already exists
│   │   ├── trace_recorder.py
│   │   └── usage_recorder.py
│   ├── repositories.py                              # merged: ToolRepository, SecretRepository
│   ├── services.py
│   └── value_objects.py
├── infra/
│   ├── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── langchain_llm_factory.py
│   │   ├── metering_usage_recorder.py
│   │   ├── observability_trace_recorder.py
│   │   ├── tools_tool_executor.py                   # replaced with direct imports
│   │   └── tools_tool_repository.py                 # replaced with direct imports
│   ├── database/
│   │   ├── __init__.py
│   │   ├── mappers.py                               # merged: tool/secret mappers
│   │   ├── models.py                                # merged: ToolModel, SecretModel (schema: agent)
│   │   ├── preflight.py
│   │   ├── repositories.py                          # merged: SQLAlchemyToolRepository, SQLAlchemySecretRepository
│   │   └── unit_of_work.py                          # merged: tools repos into AgentUnitOfWork
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── langchain_factory.py
│   │   └── providers.py
│   ├── messaging/
│   │   ├── __init__.py
│   │   ├── consumers.py                             # merged
│   │   ├── event_mappers.py                         # merged
│   │   ├── inbox_handlers.py                        # merged
│   │   └── publishers.py                            # merged
│   └── workers/
│       ├── __init__.py
│       ├── ask_job_worker.py
│       ├── inbox_consumer.py                        # merged
│       ├── inbox_processor.py                       # merged
│       ├── outbox_dispatcher.py                     # merged
│       └── registry.py                              # merged
└── presentation/
    ├── __init__.py
    ├── controllers/
    │   ├── __init__.py
    │   ├── create_tool_controller.py                 # from tools
    │   ├── update_tool_controller.py                  # from tools
    │   ├── update_tool_status_controller.py           # from tools
    │   ├── delete_tool_controller.py                  # from tools
    │   ├── test_tool_controller.py                    # from tools
    │   ├── execute_tool_controller.py                 # from tools
    │   ├── list_tools_controller.py                   # from tools
    │   ├── list_tools_by_agent_controller.py          # from tools
    │   ├── create_secret_controller.py                # from tools
    │   ├── list_secrets_controller.py                 # from tools
    │   └── ...existing agent controllers...
    ├── mappers.py                                    # merged
    ├── routes.py                                     # merged: /tools, /agents/{id}/tools, /secrets routes added
    └── schemas.py                                    # merged: tool/secret schemas
```

## Capability packages (for internal organization)

Skills/architecture allows capability sub-packages, but NOT a separate bounded context:

- `agent.tools` — tool definitions and execution (if organized as capability package)
- `agent.tool_secrets` — secret management (if organized as capability package)

However, per spec 002 rules, avoid creating a second UoW/Outbox or a new bounded context. The files listed above are organized by layer, not by a `tools` sub-module with its own UoW.
