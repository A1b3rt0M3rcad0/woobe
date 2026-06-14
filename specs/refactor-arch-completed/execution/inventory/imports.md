# Import Dependency Map

Generated: 2026-06-13
Spec: 004-create-current-import-dependency-map
Commands executed: `grep "from modules\.(ai|knowledge|runtime)" src tests`, `grep "from modules\.(metering|observability|billing|identity|tools|core)" src tests`, `grep "from (shared|src\.shared)\." src`, `grep "modules\.(ai|knowledge|runtime|...)" src/shared/workers`

## Summary

| Category | Count | Status |
|---|---|---|
| Intra-module imports (same module) | ~200+ | allowed |
| Cross-module: runtime → ai | 28 | forbidden (legacy debt, merges into agent) |
| Cross-module: runtime → knowledge | 8 | forbidden (legacy debt, merges into agent) |
| Cross-module: runtime → metering | 7 | forbidden (must use Outbox/Inbox) |
| Cross-module: runtime → observability | 8 | forbidden (must use Outbox/Inbox) |
| Cross-module: runtime → tools | 8 | forbidden (must use Outbox/Inbox) |
| Bootstrap: src/main.py → all modules | 9 | allowed (application bootstrap) |
| Bootstrap: src/workers/runner.py → runtime | 1 | forbidden (worker in wrong location) |
| Shared workers: hard-coded module lists | 2 files | forbidden (infra must not know modules) |
| Shared workers: dynamic import by event_type | 1 file | forbidden (coupled to module naming) |
| migrations/env.py → all modules | 9 | allowed (Alembic metadata requirement) |
| Modules → shared | ~100+ | allowed (shared infra usage) |
| shared → modules | 0 | allowed (correct: no reverse dependency) |
| Tests → modules | ~120+ | allowed (test imports) |

## Cross-Module Violations (src/)

### runtime → ai (will merge into agent)

| File | Line | Import | Layer violated | Migration implication |
|---|---|---|---|---|
| src/modules/runtime/service/ask_use_case.py | 13 | `from modules.ai.domain.entities import Agent, AgentRelease, ProviderCredential` | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_use_case.py | 14 | `from modules.ai.domain.errors import AgentNotFoundError, CredentialNotFoundError` | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_use_case.py | 15-19 | `from modules.ai.domain.repositories import AgentRepository, AgentReleaseRepository, ProviderCredentialRepository, AgentContractRepository, AgentModelConfigRepository` | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_use_case.py | 20 | `from modules.ai.infra.llm.langchain_factory import create_chat_model` | infra | consolidate into agent infra |
| src/modules/runtime/service/ask_use_case.py | 434,441,452,466,477,480 | `from modules.ai.domain.enums import Provider` (inline) | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_agent_stream_service.py | 15 | `from modules.ai.domain.entities import Agent, AgentRelease, ProviderCredential` | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_agent_stream_service.py | 16 | `from modules.ai.domain.errors import AgentNotFoundError, CredentialNotFoundError` | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_agent_stream_service.py | 17-21 | `from modules.ai.domain.repositories import ...` | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_agent_stream_service.py | 22 | `from modules.ai.infra.llm.langchain_factory import create_chat_model` | infra | consolidate into agent infra |
| src/modules/runtime/service/ask_agent_stream_service.py | 23-27 | `from modules.ai.infra.repositories import ...` | infra | consolidate into agent infra |
| src/modules/runtime/service/ask_agent_stream_service.py | 573,580,591,603,614,617 | `from modules.ai.domain.enums import Provider` (inline) | domain | consolidate into agent domain |
| src/modules/runtime/infra/ask_job_worker.py | 8-11 | `from modules.ai.infra.repositories import SQLAlchemyAgentRepository, ...` | infra | consolidate into agent infra |
| src/modules/runtime/application/composers/ask_agent_composer.py | 3-7 | `from modules.ai.infra.repositories import ...` | infra | consolidate into agent application |

### runtime → knowledge (will merge into agent)

| File | Line | Import | Layer violated | Migration implication |
|---|---|---|---|---|
| src/modules/runtime/service/ask_use_case.py | 21-23 | `from modules.knowledge.domain.repositories import DocumentChunkRepository, DocumentCollectionRepository` | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_agent_stream_service.py | 28-31 | `from modules.knowledge.domain.repositories import ...` | domain | consolidate into agent domain |
| src/modules/runtime/service/ask_agent_stream_service.py | 32-35 | `from modules.knowledge.infra.repositories import ...` | infra | consolidate into agent infra |
| src/modules/runtime/infra/ask_job_worker.py | 12-15 | `from modules.knowledge.infra.repositories import ...` | infra | consolidate into agent infra |
| src/modules/runtime/application/composers/ask_agent_composer.py | 8-11 | `from modules.knowledge.infra.repositories import ...` | infra | consolidate into agent application |

### runtime → metering (external module - must use Outbox/Inbox)

| File | Line | Import | Layer violated | Migration implication |
|---|---|---|---|---|
| src/modules/runtime/service/ask_use_case.py | 25 | `from modules.metering.domain.entities import UsageEvent` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_use_case.py | 26 | `from modules.metering.domain.enums import UsageEventType, UsageUnit` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_use_case.py | 27 | `from modules.metering.domain.repositories import UsageEventRepository` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_agent_stream_service.py | 36-37 | `from modules.metering.domain.entities/enums import ...` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_agent_stream_service.py | 38 | `from modules.metering.domain.repositories import UsageEventRepository` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_agent_stream_service.py | 39 | `from modules.metering.infra.repositories import SQLAlchemyUsageEventRepository` | infra | replace with event publication via Outbox |
| src/modules/runtime/infra/ask_job_worker.py | 16 | `from modules.metering.infra.repositories import SQLAlchemyUsageEventRepository` | infra | replace with event publication via Outbox |
| src/modules/runtime/application/composers/ask_agent_composer.py | 12 | `from modules.metering.infra.repositories import SQLAlchemyUsageEventRepository` | infra | replace with event publication via Outbox |

### runtime → observability (external module - must use Outbox/Inbox)

| File | Line | Import | Layer violated | Migration implication |
|---|---|---|---|---|
| src/modules/runtime/service/ask_use_case.py | 28 | `from modules.observability.domain.entities import Trace, TraceEvent` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_use_case.py | 29 | `from modules.observability.domain.enums import TraceEventType, TraceStatus` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_use_case.py | 30-33 | `from modules.observability.domain.repositories import TraceRepository, TraceEventRepository` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_agent_stream_service.py | 40-41 | `from modules.observability.domain.entities/enums import ...` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_agent_stream_service.py | 42-45 | `from modules.observability.domain.repositories import ...` | domain | replace with event publication via Outbox |
| src/modules/runtime/service/ask_agent_stream_service.py | 46-49 | `from modules.observability.infra.repositories import ...` | infra | replace with event publication via Outbox |
| src/modules/runtime/infra/ask_job_worker.py | 17-20 | `from modules.observability.infra.repositories import ...` | infra | replace with event publication via Outbox |
| src/modules/runtime/application/composers/ask_agent_composer.py | 13-15 | `from modules.observability.infra.repositories import ...` | infra | replace with event publication via Outbox |

### runtime → tools (external module - must use Outbox/Inbox or public contract)

| File | Line | Import | Layer violated | Migration implication |
|---|---|---|---|---|
| src/modules/runtime/service/ask_use_case.py | 44 | `from modules.tools.domain.repositories import ToolRepository` | domain | replace with public contract or Inbox event |
| src/modules/runtime/service/ask_use_case.py | 45 | `from modules.tools.service.tool_converter import safe_tool_name, tools_to_openai_definitions` | service | replace with public contract |
| src/modules/runtime/service/ask_use_case.py | 46 | `from modules.tools.service.use_cases import ExecuteToolUseCase` | service | replace with public contract or Inbox event |
| src/modules/runtime/service/ask_use_case.py | 47 | `from modules.tools.service.dtos import ExecuteToolInput` | service | replace with public contract |
| src/modules/runtime/service/ask_agent_stream_service.py | 69-73 | `from modules.tools.domain/infra/service import ...` | domain+infra+service | replace with public contract |
| src/modules/runtime/application/composers/ask_agent_composer.py | 26 | `from modules.tools.infra.repositories import SQLAlchemyToolRepository` | infra | replace with public contract |

### src/workers/ → modules (global workers importing module internals)

| File | Line | Import | Layer violated | Migration implication |
|---|---|---|---|---|
| src/workers/runner.py | 13 | `from modules.runtime.infra.ask_job_worker import AskJobWorker` | infra | move AskJobWorker to module worker registry |

### Shared workers: hard-coded module lists

| File | Line | Evidence | Migration implication |
|---|---|---|---|
| src/shared/workers/outbox_publisher.py | 12-15 | `MODULES = ["identity", "core", "ai", "knowledge", "runtime", "tools", "metering", "billing", "observability"]` | replace with module registry discovery |
| src/shared/workers/inbox_dispatcher.py | 14-17 | `MODULES = ["identity", "core", "ai", "knowledge", "runtime", "tools", "metering", "billing", "observability"]` | replace with module registry discovery |
| src/shared/workers/inbox_consumer.py | 10-11 | `_module_for_event_type(event_type)` + dynamic `importlib.import_module(f"modules.{module}.infra.models")` | replace with module registry discovery |

### Bootstrap imports (allowed but must be updated during migration)

| File | Line | Import | Status |
|---|---|---|---|
| src/main.py | 9 | `from modules.ai.presentation.routes import router as ai_router` | allowed (bootstrap); update to agent after migration |
| src/main.py | 13 | `from modules.knowledge.presentation.routes import router as knowledge_router` | allowed (bootstrap); update to agent after migration |
| src/main.py | 16 | `from modules.runtime.presentation.routes import router as runtime_router` | allowed (bootstrap); update to agent after migration |
| src/main.py | 10-15,17 | billing, core, identity, metering, observability, tools routers | allowed (bootstrap) |

### migrations/env.py (allowed for Alembic metadata)

| File | Line | Import | Status |
|---|---|---|---|
| migrations/env.py | 15-23 | Wildcard imports from all modules' `infra.models` | allowed (Alembic metadata); must add agent module when created |

## Intra-Module Imports (allowed - sampled)

All imports where source and target are within the same module are classified as **allowed**. Examples:

- `modules.ai.* → modules.ai.*`: ~50+ imports across domain, service, infra, presentation, application layers
- `modules.knowledge.* → modules.knowledge.*`: ~40+ imports
- `modules.runtime.* → modules.runtime.*`: ~30+ imports (excluding cross-module)
- `modules.billing.* → modules.billing.*`: ~20+ imports
- `modules.core.* → modules.core.*`: ~15+ imports
- `modules.identity.* → modules.identity.*`: ~20+ imports
- `modules.metering.* → modules.metering.*`: ~15+ imports
- `modules.observability.* → modules.observability.*`: ~15+ imports
- `modules.tools.* → modules.tools.*`: ~20+ imports

## Module → shared (allowed)

All modules correctly import from `shared` for generic infrastructure:
- `shared.domain.errors` (base error classes)
- `shared.domain.events` (OutboxEventWriter contract)
- `shared.domain.objects` (CursorPage, etc.)
- `shared.domain.time` (utc_now)
- `shared.infra.config` (Settings, UnitOfWork interface)
- `shared.infra.database` (BaseModel, session, postgres_unit_of_work)
- `shared.infra.crypto` (encrypt_secret, decrypt_secret)
- `shared.infra.rabbitmq` (RabbitMQManager)
- `shared.infra.repositories` (BaseSQLAlchemyRepository)
- `shared.infra.llm_usage` (normalize_llm_usage)
- `shared.presentation.http` (adapter, request, response)
- `shared.presentation.interface` (Controller)
- `shared.application` (TransactionalHandler)
- `shared.workers` (BaseWorker)

No `shared` module imports from any `modules.*`. This is architecturally correct.

## Test Imports (allowed with notes)

Tests import directly from modules under test. Notable cross-module test imports:

| File | Line | Import | Note |
|---|---|---|---|
| tests/unit/test_runtime/test_use_cases.py | 7 | `from modules.observability.domain.enums import TraceEventType` | tests the cross-module ask_use_case |
| tests/unit/test_runtime/test_use_cases.py | 348,376 | `from modules.tools.service.dtos import ExecuteToolOutput` | tests the cross-module ask_use_case |
| tests/unit/test_runtime/test_use_cases.py | 437 | `from modules.observability.domain.entities import TraceEvent` | tests the cross-module ask_use_case |
| tests/helpers.py | 70-136 | imports from ai, knowledge, runtime, identity, core, tools, metering, billing, observability | test factory helpers (allowed) |

## Candidate Allowlist (temporary, not applied)

The following cross-module imports exist due to the current architecture and will be resolved by the migration:

| Source | Target | Reason for allowlisting | Removal spec |
|---|---|---|---|
| runtime → ai | domain, infra | all merge into agent | 020-025 |
| runtime → knowledge | domain, infra | all merge into agent | 030-035 |
| runtime → metering | domain, infra | replace with Outbox events | 070-085 |
| runtime → observability | domain, infra | replace with Outbox events | 070-085 |
| runtime → tools | domain, service, infra | replace with public contract or Inbox | 070-085 |
| src/workers/runner.py → runtime | infra (AskJobWorker) | move to module worker registry | 060-063 |
| shared/workers → modules (dynamic) | hard-coded lists | replace with registry pattern | 050-063 |

## Risks Identified

| Risk | Severity | Evidence | Affected specs |
|---|---|---|---|
| ask_use_case.py imports 5 external modules directly | critical | Lines 13-47 of ask_use_case.py | 040-045, 070-085 |
| ask_agent_stream_service.py duplicates cross-module pattern | critical | Lines 15-73 of ask_agent_stream_service.py | 040-045, 070-085 |
| ask_job_worker.py assembles UoW spanning 5 modules | critical | Lines 8-27 of ask_job_worker.py | 074, 060-063 |
| ask_agent_composer.py imports repositories from 5 modules | high | Lines 3-26 of ask_agent_composer.py | 040-045, 074 |
| Shared workers hard-code module names | high | outbox_publisher.py:12-15, inbox_dispatcher.py:14-17 | 050-063 |
| InboxConsumer uses event_type prefix as module discovery | medium | inbox_consumer.py:10-11 | 050-063 |
