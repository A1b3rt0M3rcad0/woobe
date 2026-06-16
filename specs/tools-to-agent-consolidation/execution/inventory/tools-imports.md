# Tools Module — Import Inventory

## Imports from `modules.tools` to external modules

### `shared.*` (allowed dependencies)

| Source file | Import | Classification |
|---|---|---|
| `infra/database/models.py` | `shared.infra.database.base.BaseModel` | allowed — shared infra |
| `infra/database/models.py` | `shared.infra.database.inbox.InboxEventModel as BaseInbox` | allowed — shared infra |
| `infra/database/models.py` | `shared.infra.database.outbox.OutboxEventModel as BaseOutbox` | allowed — shared infra |
| `infra/database/repositories.py` | `shared.infra.config.interface.unit_of_work.UnitOfWork` | allowed — shared interface |
| `infra/database/repositories.py` | `shared.messaging.outbox_writer.OutboxEventWriter` | allowed — shared contract |
| `infra/database/repositories.py` | `shared.infra.objects.CursorPage` | allowed — shared object |
| `infra/database/repositories.py` | `shared.infra.repositories.base_repository.BaseSQLAlchemyRepository` | allowed — shared base |
| `infra/messaging/publishers.py` | `shared.infra.rabbitmq.RabbitMQManager` | allowed — shared infra |
| `infra/messaging/consumers.py` | `shared.infra.rabbitmq.RabbitMQManager` | allowed — shared infra |
| `infra/messaging/event_mappers.py` | *(none to shared)* | — |
| `infra/workers/registry.py` | `shared.infra.rabbitmq.RabbitMQManager` | allowed — shared infra |
| `infra/workers/registry.py` | `shared.workers.contracts.WorkerProtocol, WorkerRegistryProtocol` | allowed — shared contracts |
| `infra/workers/inbox_processor.py` | `shared.workers.inbox_processor_base.BaseInboxProcessor` | allowed — shared base |
| `infra/workers/outbox_dispatcher.py` | `shared.workers.outbox_dispatcher_base.BaseOutboxDispatcher, OutboxRecord` | allowed — shared base |
| `domain/errors.py` | `shared.infra.errors.ConflictError, NotFoundError` | allowed — shared errors |
| `domain/repositories.py` | `shared.infra.objects.CursorPage` | allowed — shared object |
| `presentation/routes.py` | `shared.presentation.http.adapter.request_adapter, response_adapter` | allowed — shared adapter |
| `application/use_cases/tools_use_cases.py` | `shared.messaging.outbox_writer.OutboxEventWriter` | allowed — shared contract |
| `application/use_cases/tools_use_cases.py` | `shared.infra.crypto.encrypt_secret` | allowed — shared utility |
| `application/use_cases/tools_use_cases.py` | `shared.infra.crypto.decrypt_secret` (dynamic import) | allowed — shared utility |

### External packages

| Source file | Import | Classification |
|---|---|---|
| `infra/messaging/publishers.py` | `aio_pika.DeliveryMode, Message` | allowed — external dependency |
| `domain/errors.py` | `uuid.UUID` | allowed — stdlib |
| `infra/database/repositories.py` | `sqlalchemy.select` | allowed — ORM dependency |
| `infra/database/models.py` | `sqlalchemy.ForeignKey, Integer, String, Text, UniqueConstraint` | allowed — ORM |
| `infra/workers/outbox_dispatcher.py` | `sqlalchemy.select, update` | allowed — ORM |
| `application/use_cases/tools_use_cases.py` | `httpx` (HTTP client) | allowed — external |

### Cross-module imports from `modules.tools.*` -> `modules.core.*`

| Source file | Import | Classification |
|---|---|---|
| `infra/database/models.py` | `ForeignKey("core.projects.id")` | **cross-schema FK** — must be removed (opaque UUID only) |

## Imports from other modules -> `modules.tools`

| Source file | Import | Classification |
|---|---|---|
| `tests/test_create_tools_worker_structure.py:6` | `from modules.tools.infra.workers.registry import ToolsWorkerRegistry` | legacy — test only |
| `tests/test_layer_dependencies.py:169` | `from modules.tools.infra.models import SecretModel` | legacy — test only (forbidden source example) |
| `tests/test_update_alembic_or_database_migrations.py:43` | `"modules.tools.infra.database.models"` | legacy — test only |
| `tests/test_update_dependency_injection_bindings.py:22` | `"modules.tools"` | legacy — test only |

All production cross-module references into `modules.tools` are **zero** (no production code outside `modules.tools` imports from it). Only test/validation code references `modules.tools`.

## Internal imports (same module)

Every file in `modules.tools` imports only from its own layers (`domain` -> `domain`, `application` -> `domain` + `application`, `infra` -> `domain` + `infra`, `presentation` -> `application` + `shared`). No production imports from other modules (`agent`, `billing`, `core`, etc.) were found.

Executed: `Select-String -Pattern "modules\.tools" -Path "src/**/*.py","tests/**/*.py","migrations/**/*.py"`
Exit code: 0
