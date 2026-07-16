# Current import and dependency map

- `src/main.py` imports public route entrypoints from `src/modules/*/presentation/routes.py`.
- `src/modules/identity/presentation/` depends on identity application services and shared security dependencies.
- `src/modules/core/presentation/` depends on core application composers and DTOs.
- `src/modules/agent/presentation/` depends on agent application use cases and streaming controllers.
- `src/modules/observability/presentation/` depends on observability application queries.
- `src/modules/*/application/` may depend on its own domain and shared abstractions.
- `src/modules/*/domain/` must not import presentation or infrastructure packages.
- `src/modules/*/infra/` implements application and domain ports using SQLAlchemy, RabbitMQ and HTTP clients.
- `src/shared/security/` is imported by presentation guards and runtime authentication adapters.
- `src/shared/infra/database/` is imported by module-specific infrastructure models.
- `src/shared/workers/` depends on worker protocols and module registry entrypoints.
- `src/modules/agent/application/use_cases/runtime_streaming.py` contains provider-independent stream orchestration.
- `src/modules/agent/infra/adapters/tool_executor.py` implements bounded HTTP tool execution.
- `src/modules/core/infra/database/project_overview_reader.py` implements the overview read port.
- `src/modules/identity/infra/database/` implements session and membership persistence.
- Legacy import names `modules.ai`, `modules.knowledge` and `modules.runtime` are absent from the current graph.
- The former standalone tools context is consolidated under `src/modules/agent/`.
- Tests in `tests/architecture/` enforce the active dependency direction.
