# Runtime to Agent Migration Map

Spec: `040-map-runtime-to-agent`
Date: 2026-06-14
Agent: opencode/deepseek-v4-pro

## Summary

| Category | File count | Target layer |
|---|---|---|
| Domain | 5 | `agent/domain` |
| Service (use cases, DTOs) | 5 | `agent/application/use_cases`, `agent/application/dtos` |
| Application/Composers | 9 | `agent/application/composers` |
| Infra (models, repos, mappers) | 4 | `agent/infra/database` |
| Infra (worker) | 1 | `agent/infra/workers` |
| Presentation (routes, schemas) | 3 | `agent/presentation` |
| Presentation/Controllers | 9 | `agent/presentation/controllers` |
| **Total** | **36** | |

## Domain Layer

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/runtime/domain/__init__.py` | `src/modules/agent/domain/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/runtime/domain/entities.py` | `src/modules/agent/domain/entities.py` (merge) | domain entities (Session, Message, AskJob) | runtime.service.*, runtime.infra.*, tests | all /runtime routes | - | medium — ask_use_case and ask_agent_stream_service depend on these | test entity instantiation after move |
| `src/modules/runtime/domain/enums.py` | `src/modules/agent/domain/enums.py` (merge) | domain enums (SessionStatus, MessageRole, SessionMode) | runtime.service.dtos, runtime.presentation.schemas, runtime.infra.mappers | all /runtime routes | - | low | test enum availability after move |
| `src/modules/runtime/domain/errors.py` | `src/modules/agent/domain/errors.py` (merge) | domain errors (SessionNotFoundError, MessageNotFoundError, AskJobNotFoundError) | runtime.infra.repositories | - | - | low | test error classes exist after move |
| `src/modules/runtime/domain/repositories.py` | `src/modules/agent/domain/repositories.py` (merge) | repository interfaces (SessionRepository, MessageRepository, AskJobRepository) | runtime.service.use_cases, runtime.service.ask_use_case, runtime.service.ask_agent_stream_service, runtime.infra.repositories | all /runtime routes | - | medium — cross-module consumers via ask_use_case | test interface availability after move |

## Application Layer — Composers

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/runtime/application/__init__.py` | `src/modules/agent/application/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/runtime/application/composers/__init__.py` | `src/modules/agent/application/composers/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/runtime/application/composers/ask_agent_composer.py` | `src/modules/agent/application/composers/ask_agent_composer.py` | composer | runtime.presentation.routes | POST /runtime/ask | - | high — imports repos from ai, knowledge, metering, observability, tools | route handler test |
| `src/modules/runtime/application/composers/ask_agent_stream_composer.py` | `src/modules/agent/application/composers/ask_agent_stream_composer.py` | composer | runtime.presentation.routes | POST /runtime/ask/stream | - | high — imports repos from ai, knowledge, metering, observability, tools | route handler test |
| `src/modules/runtime/application/composers/create_ask_job_composer.py` | `src/modules/agent/application/composers/create_ask_job_composer.py` | composer | runtime.presentation.routes | POST /runtime/ask/jobs | - | low | route handler test |
| `src/modules/runtime/application/composers/create_session_composer.py` | `src/modules/agent/application/composers/create_session_composer.py` | composer | runtime.presentation.routes | POST /runtime/sessions | - | low | route handler test |
| `src/modules/runtime/application/composers/get_ask_job_composer.py` | `src/modules/agent/application/composers/get_ask_job_composer.py` | composer | runtime.presentation.routes | GET /runtime/ask/jobs/{id} | - | low | route handler test |
| `src/modules/runtime/application/composers/list_agent_sessions_composer.py` | `src/modules/agent/application/composers/list_agent_sessions_composer.py` | composer | runtime.presentation.routes | GET /runtime/agents/{id}/sessions | - | low | route handler test |
| `src/modules/runtime/application/composers/list_messages_composer.py` | `src/modules/agent/application/composers/list_messages_composer.py` | composer | runtime.presentation.routes | GET /runtime/sessions/{id}/messages | - | low | route handler test |
| `src/modules/runtime/application/composers/send_message_composer.py` | `src/modules/agent/application/composers/send_message_composer.py` | composer | runtime.presentation.routes | POST /runtime/messages | - | low | route handler test |

## Service Layer (maps to Application)

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/runtime/service/__init__.py` | `src/modules/agent/application/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/runtime/service/dtos.py` | `src/modules/agent/application/dtos/runtime_dtos.py` | DTOs (12 classes: CreateSessionInput/Output, SendMessageInput/Output, MessageResponse, ListMessagesInput/Output, ListAgentSessionsInput/Output, AskInput, AskOutput, UsageInfo, SourceInfo, ToolCallInfo, CreateAskJobInput/Output, GetAskJobOutput) | runtime.service.use_cases, runtime.service.ask_use_case, runtime.service.ask_agent_stream_service, runtime.presentation.controllers | all /runtime routes | - | low | DTO instantiation test |
| `src/modules/runtime/service/use_cases.py` | `src/modules/agent/application/use_cases/runtime_use_cases.py` | use cases (6 classes: CreateSessionUseCase, SendMessageUseCase, ListMessagesUseCase, ListAgentSessionsUseCase, CreateAskJobUseCase, GetAskJobUseCase) | runtime.application.composers, tests/unit/test_runtime | all /runtime routes | writes to runtime.outbox_events | medium — produces events | unit test use case execution |
| `src/modules/runtime/service/ask_use_case.py` | `src/modules/agent/application/use_cases/ask_use_case.py` | orchestration use case (AskAgentUseCase) | runtime.application.composers.ask_agent_composer, runtime.infra.ask_job_worker | POST /runtime/ask, POST /runtime/ask/jobs | runtime.outbox_events, metering.usage_events, observability.traces | critical — imports ai, knowledge, metering, observability, tools directly | integration test; cross-module imports must become internal (ai, knowledge) or Inbox-based (metering, observability, tools) |
| `src/modules/runtime/service/ask_agent_stream_service.py` | `src/modules/agent/application/use_cases/ask_agent_stream_service.py` | streaming orchestration service (AskAgentStreamService) | runtime.application.composers.ask_agent_stream_composer | POST /runtime/ask/stream | runtime.outbox_events, metering.usage_events, observability.traces | critical — imports ai, knowledge, metering, observability, tools directly; uses concrete infra repos | streaming test; cross-module imports must become internal or Inbox-based |

## Infra Layer — Database

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/runtime/infra/__init__.py` | `src/modules/agent/infra/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/runtime/infra/models.py` | `src/modules/agent/infra/database/models.py` (merge) | SQLAlchemy models (SessionModel, MessageModel, AskJobModel, OutboxEventModel, InboxEventModel) | migrations/env.py, shared/workers (dynamic), runtime.infra.repositories | all /runtime routes | runtime.sessions, runtime.messages, runtime.ask_jobs, runtime.outbox_events, runtime.inbox_events | high — schema rename requires expand-migrate-contract; FKs to core.projects and ai.agents | model import test |
| `src/modules/runtime/infra/mappers.py` | `src/modules/agent/infra/database/mappers.py` (merge) | entity-model mappers (6 functions: session_to_model, model_to_session, message_to_model, model_to_message, ask_job_to_model, model_to_ask_job) | runtime.infra.repositories | all /runtime routes | - | low | mapper function test |
| `src/modules/runtime/infra/repositories.py` | `src/modules/agent/infra/database/repositories.py` (merge) | SQLAlchemy repositories (SQLAlchemySessionRepository, SQLAlchemyMessageRepository, SQLAlchemyAskJobRepository, SQLAlchemyOutboxEventWriter) | runtime.application.composers, runtime.infra.ask_job_worker, runtime.service.ask_agent_stream_service | all /runtime routes | - | medium — ask_job_worker uses shared PostgresUnitOfWork cross-module | repository import test |

## Infra Layer — Worker

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/runtime/infra/ask_job_worker.py` | `src/modules/agent/infra/workers/ask_job_worker.py` | concrete worker (AskJobWorker) | src/workers/runner.py (direct import) | background job execution | - | critical — imports repos from ai, knowledge, metering, observability; uses PostgresUnitOfWork cross-module; does not inherit BaseWorker | worker test; must be refactored to use agent-internal UoW (spec 074) |

## Presentation Layer

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/runtime/presentation/__init__.py` | `src/modules/agent/presentation/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/runtime/presentation/routes.py` | `src/modules/agent/presentation/routes.py` (merge) | FastAPI router (7 routes, prefix=/runtime) | src/main.py (bootstrap) | all 7 /runtime routes | - | medium — prefix change needs shim | route registration test |
| `src/modules/runtime/presentation/schemas.py` | `src/modules/agent/presentation/schemas.py` (merge) | Pydantic schemas | runtime.presentation.controllers | all /runtime routes | - | low | schema validation test |

## Presentation Layer — Controllers

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/runtime/presentation/controllers/__init__.py` | `src/modules/agent/presentation/controllers/__init__.py` (merge) | package init | none | - | - | low | import test |
| `src/modules/runtime/presentation/controllers/ask_agent_controller.py` | `src/modules/agent/presentation/controllers/ask_agent_controller.py` | controller | runtime.presentation.routes | POST /runtime/ask | - | low | controller test |
| `src/modules/runtime/presentation/controllers/ask_agent_stream_controller.py` | `src/modules/agent/presentation/controllers/ask_agent_stream_controller.py` | controller | runtime.presentation.routes | POST /runtime/ask/stream | - | low | controller test |
| `src/modules/runtime/presentation/controllers/create_ask_job_controller.py` | `src/modules/agent/presentation/controllers/create_ask_job_controller.py` | controller | runtime.presentation.routes | POST /runtime/ask/jobs | - | low | controller test |
| `src/modules/runtime/presentation/controllers/create_session_controller.py` | `src/modules/agent/presentation/controllers/create_session_controller.py` | controller | runtime.presentation.routes | POST /runtime/sessions | - | low | controller test |
| `src/modules/runtime/presentation/controllers/get_ask_job_controller.py` | `src/modules/agent/presentation/controllers/get_ask_job_controller.py` | controller | runtime.presentation.routes | GET /runtime/ask/jobs/{id} | - | low | controller test |
| `src/modules/runtime/presentation/controllers/list_agent_sessions_controller.py` | `src/modules/agent/presentation/controllers/list_agent_sessions_controller.py` | controller | runtime.presentation.routes | GET /runtime/agents/{id}/sessions | - | low | controller test |
| `src/modules/runtime/presentation/controllers/list_messages_controller.py` | `src/modules/agent/presentation/controllers/list_messages_controller.py` | controller | runtime.presentation.routes | GET /runtime/sessions/{id}/messages | - | low | controller test |
| `src/modules/runtime/presentation/controllers/send_message_controller.py` | `src/modules/agent/presentation/controllers/send_message_controller.py` | controller | runtime.presentation.routes | POST /runtime/messages | - | low | controller test |

## Database Tables (Schema: runtime → agent)

| Table | Current Schema | Target Schema | Model | FKs intra-module | FKs cross-module (blocker) | Risk | Migration spec |
|---|---|---|---|---|---|---|---|
| sessions | runtime | agent | SessionModel | - | project_id → core.projects.id, agent_id → ai.agents.id (becomes intra-module after consolidation) | medium | 134 |
| messages | runtime | agent | MessageModel | session_id → runtime.sessions.id (intra) | project_id → core.projects.id, agent_id → ai.agents.id (becomes intra-module) | medium | 134 |
| ask_jobs | runtime | agent | AskJobModel | session_id → runtime.sessions.id (intra) | project_id → core.projects.id, agent_id → ai.agents.id (becomes intra-module) | medium | 134 |
| outbox_events | runtime | agent | OutboxEventModel | - | - | medium — merge with ai/knowledge outbox | 070-076 |
| inbox_events | runtime | agent | InboxEventModel | - | - | medium — merge with ai/knowledge inbox | 070-076 |

## Events Produced

| event_type | aggregate_type | Producer use case | Current schema | Target schema | Routing impact | Risk |
|---|---|---|---|---|---|---|
| `runtime.session.created` | session | CreateSessionUseCase | runtime.outbox_events | agent.outbox_events | InboxConsumer routes to "runtime" (current module) | low — correct prefix |
| `runtime.ask.completed` | message | SendMessageUseCase | runtime.outbox_events | agent.outbox_events | InboxConsumer routes to "runtime" (current module) | low — correct prefix |
| `usage_event.recorded` | usage_event | AskAgentUseCase, AskAgentStreamService | runtime.outbox_events | agent.outbox_events | InboxConsumer routes to "usage_event" (fails — no such module) | high — produces event of metering domain; must be moved to metering outbox or converted to agent→metering Inbox event |

## External Consumers of Runtime Module

| Consumer file | Import path | Symbols used | Resolution strategy |
|---|---|---|---|
| `src/main.py` | `modules.runtime.presentation.routes` | router (as runtime_router) | Update bootstrap to agent (spec 130-131) |
| `src/workers/runner.py` | `modules.runtime.infra.ask_job_worker` | AskJobWorker | Move worker to agent/infra/workers; update runner via registry (specs 054, 063) |
| `migrations/env.py` | `modules.runtime.infra.models` | (metadata) | Update to agent (spec 134) |
| `src/shared/workers/outbox_publisher.py` | dynamic: module list includes "runtime" | OutboxEventModel | Replace with registry (specs 050-063) |
| `src/shared/workers/inbox_dispatcher.py` | dynamic: module list includes "runtime" | InboxEventModel | Replace with registry (specs 050-063) |
| `tests/unit/test_runtime/*` | `modules.runtime.*` | all test imports | Update to agent after move |

## Cross-Module Dependencies (Critical)

| File | External module imported | Symbols | Becomes after consolidation | Resolution spec |
|---|---|---|---|---|
| `runtime/service/ask_use_case.py` | ai.domain.entities | Agent, ProviderCredential, etc. | internal (same module) | 041-045 |
| `runtime/service/ask_use_case.py` | ai.domain.repositories | AgentRepository, ProviderCredentialRepository | internal (same module) | 041-045 |
| `runtime/service/ask_use_case.py` | ai.infra.llm.langchain_factory | LangchainFactory | internal (same module) | 041-045 |
| `runtime/service/ask_use_case.py` | knowledge.domain.repositories | AgentCollectionRepository, DocumentChunkRepository | internal (same module) | 041-045 |
| `runtime/service/ask_use_case.py` | metering.domain.* | UsageRecord, repos | cross-module — needs Outbox/Inbox | 070-085 |
| `runtime/service/ask_use_case.py` | observability.domain.* | Trace, repos | cross-module — needs Outbox/Inbox | 070-085 |
| `runtime/service/ask_use_case.py` | tools.* | ToolRepository, use_cases | cross-module — needs public contract or Inbox | 070-085 |
| `runtime/service/ask_agent_stream_service.py` | ai.* | same as ask_use_case | internal (same module) | 041-045 |
| `runtime/service/ask_agent_stream_service.py` | knowledge.* | same as ask_use_case + infra repos | internal (same module) | 041-045 |
| `runtime/service/ask_agent_stream_service.py` | metering.* | same as ask_use_case + infra repos | cross-module — needs Outbox/Inbox | 070-085 |
| `runtime/service/ask_agent_stream_service.py` | observability.* | same as ask_use_case + infra repos | cross-module — needs Outbox/Inbox | 070-085 |
| `runtime/service/ask_agent_stream_service.py` | tools.* | same as ask_use_case + infra repos | cross-module — needs public contract or Inbox | 070-085 |
| `runtime/infra/ask_job_worker.py` | ai.infra.repositories | concrete repos | internal (same module) | 041-045 |
| `runtime/infra/ask_job_worker.py` | knowledge.infra.repositories | concrete repos | internal (same module) | 041-045 |
| `runtime/infra/ask_job_worker.py` | metering.infra.repositories | concrete repos | cross-module — needs Outbox/Inbox | 070-085 |
| `runtime/infra/ask_job_worker.py` | observability.infra.repositories | concrete repos | cross-module — needs Outbox/Inbox | 070-085 |

## Route Migration Plan

| Current route | Target route | Shim required | Shim removal spec |
|---|---|---|---|
| `/runtime/sessions` | `/agent/sessions` | yes — redirect/proxy | 142 |
| `/runtime/agents/{id}/sessions` | `/agent/agents/{id}/sessions` | yes — redirect/proxy | 142 |
| `/runtime/ask` | `/agent/ask` | yes — redirect/proxy | 142 |
| `/runtime/ask/stream` | `/agent/ask/stream` | yes — redirect/proxy | 142 |
| `/runtime/ask/jobs` | `/agent/ask/jobs` | yes — redirect/proxy | 142 |
| `/runtime/ask/jobs/{id}` | `/agent/ask/jobs/{id}` | yes — redirect/proxy | 142 |
| `/runtime/sessions/{id}/messages` | `/agent/sessions/{id}/messages` | yes — redirect/proxy | 142 |

## Risk Summary

| Risk | Severity | Mitigation | Responsible spec |
|---|---|---|---|
| ask_use_case imports 5 external modules directly | critical | ai+knowledge become internal after agent consolidation; metering+observability+tools must move to Outbox/Inbox | 041-045 (internal), 070-085 (cross-module) |
| ask_agent_stream_service imports concrete infra repos from 5 modules | critical | Same as above; additionally uses concrete repos instead of domain interfaces | 041-045, 070-085 |
| ask_job_worker uses PostgresUnitOfWork coordinating 5 modules | critical | Replace with AgentUnitOfWork (agent-only) + event publishing for metering/observability | 074, 085 |
| ask_job_worker imported directly by src/workers/runner.py | high | Move to agent/infra/workers; register via worker registry | 054, 063, 085 |
| ask_job_worker does not inherit BaseWorker | medium | Refactor to inherit BaseWorker or implement worker contract | 085 |
| Schema rename runtime→agent requires expand-migrate-contract | high | Physical schema change deferred to spec 134 | 134 |
| runtime produces usage_event.recorded (metering domain event) | high | After consolidation into agent, this becomes agent producing metering events — resolve via Outbox pattern to metering inbox | 070-085 |
| 7 routes under /runtime need shim to /agent | medium | Create shim during route migration, remove at spec 142 | 044, 131, 142 |
| shared/workers hard-codes "runtime" in module list | medium | Replace with registry pattern | 050-063 |
| 2 runtime events have correct "runtime." prefix (unlike knowledge/ai events) | low (positive) | Inbox routing works for runtime events; rename to "agent." during event standardization | 100-109 |

## Migration Order

The runtime module should be migrated layer by layer per specs 041-045:

1. **Spec 041** — Move runtime domain to agent domain (entities, enums, errors, repositories)
2. **Spec 042** — Move runtime application to agent application (use cases, DTOs, ask_use_case, ask_agent_stream_service, composers)
3. **Spec 043** — Move runtime infra to agent infra (models, repositories, mappers, ask_job_worker)
4. **Spec 044** — Move runtime presentation to agent presentation (routes, schemas, controllers)
5. **Spec 045** — Update all runtime imports to agent imports (shims, tests, bootstrap)

No physical file should be moved until specs 041+ are activated.

## Special Notes

- `ask_use_case.py` and `ask_agent_stream_service.py` are the most complex files in the runtime module (900+ and 1000+ lines respectively). They orchestrate the full ask flow including LLM calls, tool execution, knowledge retrieval, session management, message persistence, usage tracking, and trace recording.
- After moving to agent, the imports from `modules.ai` and `modules.knowledge` become internal agent imports (resolved). But imports from `modules.metering`, `modules.observability`, and `modules.tools` remain cross-module violations that must be resolved via Outbox/Inbox in specs 070-085.
- The `ask_job_worker.py` coordinates a shared PostgresUnitOfWork across multiple modules' repositories. This is the most severe UoW violation in the codebase and must be replaced by AgentUnitOfWork (spec 074) plus event-based communication for cross-module state changes.
