# AI to Agent Migration Map

Spec: `020-map-ai-to-agent`
Date: 2026-06-13
Agent: opencode/deepseek-v4-pro

## Summary

| Category | File count | Target layer |
|---|---|---|
| Domain | 5 | `agent/domain` |
| Application/Composers | 27 | `agent/application/composers` |
| Service (use cases, DTOs) | 3 | `agent/application/use_cases`, `agent/application/dtos` |
| Infra (models, repos, mappers) | 4 | `agent/infra/database` |
| Infra LLM | 2 | `agent/infra/llm` |
| Presentation (routes, schemas, mappers) | 4 | `agent/presentation` |
| Presentation/Controllers | 26 | `agent/presentation/controllers` |
| **Total** | **71** | |

## Domain Layer

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/ai/domain/__init__.py` | `src/modules/agent/domain/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/ai/domain/entities.py` | `src/modules/agent/domain/entities.py` (merge) | domain entities (Agent, AgentRelease, ProviderCredential, AgentPrompt, AgentContract, AgentModelConfig, AgentReleaseTest) | runtime.service.ask_use_case, runtime.service.ask_agent_stream_service | all /ai routes | - | high — runtime imports these directly | test entity instantiation after move |
| `src/modules/ai/domain/enums.py` | `src/modules/agent/domain/enums.py` (merge) | domain enums (Provider, AgentStatus, ReleaseStatus, ReleaseTestStatus) | runtime.service.ask_use_case (inline imports of Provider) | all /ai routes | - | medium — inline imports in runtime | test enum availability after move |
| `src/modules/ai/domain/errors.py` | `src/modules/agent/domain/errors.py` (merge) | domain errors (AgentNotFoundError, CredentialNotFoundError, ReleaseNotFoundError, etc.) | runtime.service.ask_use_case, runtime.service.ask_agent_stream_service | - | - | medium | test error classes exist after move |
| `src/modules/ai/domain/repositories.py` | `src/modules/agent/domain/repositories.py` (merge) | repository interfaces (AgentRepository, AgentReleaseRepository, ProviderCredentialRepository, AgentContractRepository, AgentModelConfigRepository, AgentPromptRepository, AgentReleaseTestRepository) | runtime.service.ask_use_case, runtime.service.ask_agent_stream_service, runtime.infra.ask_job_worker, runtime.application.composers.ask_agent_composer | all /ai routes | - | high — most consumed ai artifact | test interface availability after move |

## Application Layer — Composers

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/ai/application/__init__.py` | `src/modules/agent/application/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/ai/application/composers/__init__.py` | `src/modules/agent/application/composers/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/ai/application/composers/create_agent_composer.py` | `src/modules/agent/application/composers/create_agent_composer.py` | composer | ai.presentation.routes | POST /ai/agents | - | low | route handler test |
| `src/modules/ai/application/composers/create_contract_version_composer.py` | `src/modules/agent/application/composers/create_contract_version_composer.py` | composer | ai.presentation.routes | POST /ai/agents/{id}/contracts | - | low | route handler test |
| `src/modules/ai/application/composers/create_model_config_composer.py` | `src/modules/agent/application/composers/create_model_config_composer.py` | composer | ai.presentation.routes | POST /ai/agents/{id}/model-configs | - | low | route handler test |
| `src/modules/ai/application/composers/create_prompt_version_composer.py` | `src/modules/agent/application/composers/create_prompt_version_composer.py` | composer | ai.presentation.routes | POST /ai/agents/{id}/prompts | - | low | route handler test |
| `src/modules/ai/application/composers/create_provider_credential_composer.py` | `src/modules/agent/application/composers/create_provider_credential_composer.py` | composer | ai.presentation.routes | POST /ai/credentials | - | low | route handler test |
| `src/modules/ai/application/composers/create_release_composer.py` | `src/modules/agent/application/composers/create_release_composer.py` | composer | ai.presentation.routes | POST /ai/agents/{id}/releases | - | low | route handler test |
| `src/modules/ai/application/composers/create_release_test_composer.py` | `src/modules/agent/application/composers/create_release_test_composer.py` | composer | ai.presentation.routes | POST /ai/agents/{id}/release-tests | - | low | route handler test |
| `src/modules/ai/application/composers/delete_release_composer.py` | `src/modules/agent/application/composers/delete_release_composer.py` | composer | ai.presentation.routes | DELETE /ai/agents/{id}/releases/{rid} | - | low | route handler test |
| `src/modules/ai/application/composers/get_agent_composer.py` | `src/modules/agent/application/composers/get_agent_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id} | - | low | route handler test |
| `src/modules/ai/application/composers/get_contract_version_composer.py` | `src/modules/agent/application/composers/get_contract_version_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/contracts/{cid} | - | low | route handler test |
| `src/modules/ai/application/composers/get_model_config_composer.py` | `src/modules/agent/application/composers/get_model_config_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/model-configs/{mid} | - | low | route handler test |
| `src/modules/ai/application/composers/get_prompt_version_composer.py` | `src/modules/agent/application/composers/get_prompt_version_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/prompts/{vid} | - | low | route handler test |
| `src/modules/ai/application/composers/get_release_composer.py` | `src/modules/agent/application/composers/get_release_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/releases/{rid} | - | low | route handler test |
| `src/modules/ai/application/composers/list_agents_composer.py` | `src/modules/agent/application/composers/list_agents_composer.py` | composer | ai.presentation.routes | GET /ai/agents | - | low | route handler test |
| `src/modules/ai/application/composers/list_contract_versions_composer.py` | `src/modules/agent/application/composers/list_contract_versions_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/contracts | - | low | route handler test |
| `src/modules/ai/application/composers/list_model_configs_composer.py` | `src/modules/agent/application/composers/list_model_configs_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/model-configs | - | low | route handler test |
| `src/modules/ai/application/composers/list_prompt_versions_composer.py` | `src/modules/agent/application/composers/list_prompt_versions_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/prompts | - | low | route handler test |
| `src/modules/ai/application/composers/list_provider_credentials_composer.py` | `src/modules/agent/application/composers/list_provider_credentials_composer.py` | composer | ai.presentation.routes | GET /ai/credentials | - | low | route handler test |
| `src/modules/ai/application/composers/list_release_tests_composer.py` | `src/modules/agent/application/composers/list_release_tests_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/releases/{rid}/tests | - | low | route handler test |
| `src/modules/ai/application/composers/list_releases_composer.py` | `src/modules/agent/application/composers/list_releases_composer.py` | composer | ai.presentation.routes | GET /ai/agents/{id}/releases | - | low | route handler test |
| `src/modules/ai/application/composers/promote_release_composer.py` | `src/modules/agent/application/composers/promote_release_composer.py` | composer | ai.presentation.routes | POST /ai/agents/{id}/releases/{rid}/promote | - | low | route handler test |
| `src/modules/ai/application/composers/rollback_release_composer.py` | `src/modules/agent/application/composers/rollback_release_composer.py` | composer | ai.presentation.routes | POST /ai/agents/{id}/releases/{rid}/rollback | - | low | route handler test |
| `src/modules/ai/application/composers/update_agent_composer.py` | `src/modules/agent/application/composers/update_agent_composer.py` | composer | ai.presentation.routes | PATCH /ai/agents/{id} | - | low | route handler test |
| `src/modules/ai/application/composers/update_contract_version_composer.py` | `src/modules/agent/application/composers/update_contract_version_composer.py` | composer | ai.presentation.routes | PATCH /ai/agents/{id}/contracts/{cid} | - | low | route handler test |
| `src/modules/ai/application/composers/update_provider_credential_composer.py` | `src/modules/agent/application/composers/update_provider_credential_composer.py` | composer | ai.presentation.routes | PATCH /ai/credentials/{id} | - | low | route handler test |

## Service Layer (maps to Application)

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/ai/service/__init__.py` | `src/modules/agent/application/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/ai/service/dtos.py` | `src/modules/agent/application/dtos/ai_dtos.py` | DTOs | ai.service.use_cases, ai.presentation.controllers | all /ai routes | - | low | DTO instantiation test |
| `src/modules/ai/service/use_cases.py` | `src/modules/agent/application/use_cases/ai_use_cases.py` | use cases (CreateAgentUseCase, UpdateAgentUseCase, CreateProviderCredentialUseCase, etc.) | ai.application.composers, tests/unit/test_ai/test_use_cases.py | all /ai routes | writes to ai.outbox_events | medium — produces events | unit test use case execution |

## Infra Layer — Database

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/ai/infra/__init__.py` | `src/modules/agent/infra/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/ai/infra/models.py` | `src/modules/agent/infra/database/models.py` (merge) | SQLAlchemy models (ProviderCredentialModel, AgentModel, AgentPromptModel, AgentContractModel, AgentModelConfigModel, AgentReleaseModel, AgentReleaseTestModel, OutboxEventModel, InboxEventModel) | runtime.infra.ask_job_worker (indirect via repos), migrations/env.py, shared/workers (dynamic import) | all /ai routes | ai.provider_credentials, ai.agents, ai.agent_prompts, ai.agent_contracts, ai.agent_model_configs, ai.agent_releases, ai.agent_release_tests, ai.outbox_events, ai.inbox_events | high — schema rename requires expand-migrate-contract | model import test |
| `src/modules/ai/infra/repositories.py` | `src/modules/agent/infra/database/repositories.py` (merge) | SQLAlchemy repositories (SQLAlchemyAgentRepository, SQLAlchemyAgentReleaseRepository, SQLAlchemyProviderCredentialRepository, SQLAlchemyAgentContractRepository, SQLAlchemyAgentModelConfigRepository, SQLAlchemyAgentPromptRepository, SQLAlchemyAgentReleaseTestRepository) | runtime.infra.ask_job_worker, runtime.application.composers.ask_agent_composer, runtime.service.ask_agent_stream_service | all /ai routes | - | high — cross-module consumer imports | repository import test |
| `src/modules/ai/infra/mappers.py` | `src/modules/agent/infra/database/mappers.py` (merge) | entity-model mappers | ai.infra.repositories | all /ai routes | - | low | mapper function test |

## Infra Layer — LLM

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/ai/infra/llm/__init__.py` | `src/modules/agent/infra/llm/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/ai/infra/llm/langchain_factory.py` | `src/modules/agent/infra/llm/langchain_factory.py` | LLM factory (create_chat_model) | runtime.service.ask_use_case, runtime.service.ask_agent_stream_service | POST /runtime/ask, POST /runtime/ask/stream | - | high — cross-module consumer imports | factory function test |

## Presentation Layer

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/ai/presentation/__init__.py` | `src/modules/agent/presentation/__init__.py` (merge) | package init | none external | - | - | low | import test |
| `src/modules/ai/presentation/routes.py` | `src/modules/agent/presentation/routes.py` (merge) | FastAPI router (25 routes, prefix=/ai) | src/main.py (bootstrap) | all 25 /ai routes | - | medium — prefix change needs shim | route registration test |
| `src/modules/ai/presentation/schemas.py` | `src/modules/agent/presentation/schemas.py` (merge) | Pydantic schemas | ai.presentation.controllers | all /ai routes | - | low | schema validation test |
| `src/modules/ai/presentation/mappers.py` | `src/modules/agent/presentation/mappers.py` (merge) | response mappers | ai.presentation.controllers | all /ai routes | - | low | mapper test |

## Presentation Layer — Controllers

| Origin | Destination | Artifact type | Consumer imports | Affected route | Table/Schema | Risk | Minimum test |
|---|---|---|---|---|---|---|---|
| `src/modules/ai/presentation/controllers/__init__.py` | `src/modules/agent/presentation/controllers/__init__.py` (merge) | package init | none | - | - | low | import test |
| `src/modules/ai/presentation/controllers/create_agent_controller.py` | `src/modules/agent/presentation/controllers/create_agent_controller.py` | controller | ai.presentation.routes | POST /ai/agents | - | low | controller test |
| `src/modules/ai/presentation/controllers/create_contract_version_controller.py` | `src/modules/agent/presentation/controllers/create_contract_version_controller.py` | controller | ai.presentation.routes | POST /ai/agents/{id}/contracts | - | low | controller test |
| `src/modules/ai/presentation/controllers/create_model_config_controller.py` | `src/modules/agent/presentation/controllers/create_model_config_controller.py` | controller | ai.presentation.routes | POST /ai/agents/{id}/model-configs | - | low | controller test |
| `src/modules/ai/presentation/controllers/create_prompt_version_controller.py` | `src/modules/agent/presentation/controllers/create_prompt_version_controller.py` | controller | ai.presentation.routes | POST /ai/agents/{id}/prompts | - | low | controller test |
| `src/modules/ai/presentation/controllers/create_provider_credential_controller.py` | `src/modules/agent/presentation/controllers/create_provider_credential_controller.py` | controller | ai.presentation.routes | POST /ai/credentials | - | low | controller test |
| `src/modules/ai/presentation/controllers/create_release_controller.py` | `src/modules/agent/presentation/controllers/create_release_controller.py` | controller | ai.presentation.routes | POST /ai/agents/{id}/releases | - | low | controller test |
| `src/modules/ai/presentation/controllers/create_release_test_controller.py` | `src/modules/agent/presentation/controllers/create_release_test_controller.py` | controller | ai.presentation.routes | POST /ai/agents/{id}/release-tests | - | low | controller test |
| `src/modules/ai/presentation/controllers/delete_release_controller.py` | `src/modules/agent/presentation/controllers/delete_release_controller.py` | controller | ai.presentation.routes | DELETE /ai/agents/{id}/releases/{rid} | - | low | controller test |
| `src/modules/ai/presentation/controllers/get_agent_controller.py` | `src/modules/agent/presentation/controllers/get_agent_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id} | - | low | controller test |
| `src/modules/ai/presentation/controllers/get_contract_version_controller.py` | `src/modules/agent/presentation/controllers/get_contract_version_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/contracts/{cid} | - | low | controller test |
| `src/modules/ai/presentation/controllers/get_model_config_controller.py` | `src/modules/agent/presentation/controllers/get_model_config_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/model-configs/{mid} | - | low | controller test |
| `src/modules/ai/presentation/controllers/get_prompt_version_controller.py` | `src/modules/agent/presentation/controllers/get_prompt_version_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/prompts/{vid} | - | low | controller test |
| `src/modules/ai/presentation/controllers/get_release_controller.py` | `src/modules/agent/presentation/controllers/get_release_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/releases/{rid} | - | low | controller test |
| `src/modules/ai/presentation/controllers/list_agents_controller.py` | `src/modules/agent/presentation/controllers/list_agents_controller.py` | controller | ai.presentation.routes | GET /ai/agents | - | low | controller test |
| `src/modules/ai/presentation/controllers/list_contract_versions_controller.py` | `src/modules/agent/presentation/controllers/list_contract_versions_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/contracts | - | low | controller test |
| `src/modules/ai/presentation/controllers/list_model_configs_controller.py` | `src/modules/agent/presentation/controllers/list_model_configs_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/model-configs | - | low | controller test |
| `src/modules/ai/presentation/controllers/list_prompt_versions_controller.py` | `src/modules/agent/presentation/controllers/list_prompt_versions_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/prompts | - | low | controller test |
| `src/modules/ai/presentation/controllers/list_provider_credentials_controller.py` | `src/modules/agent/presentation/controllers/list_provider_credentials_controller.py` | controller | ai.presentation.routes | GET /ai/credentials | - | low | controller test |
| `src/modules/ai/presentation/controllers/list_release_tests_controller.py` | `src/modules/agent/presentation/controllers/list_release_tests_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/releases/{rid}/tests | - | low | controller test |
| `src/modules/ai/presentation/controllers/list_releases_controller.py` | `src/modules/agent/presentation/controllers/list_releases_controller.py` | controller | ai.presentation.routes | GET /ai/agents/{id}/releases | - | low | controller test |
| `src/modules/ai/presentation/controllers/promote_release_controller.py` | `src/modules/agent/presentation/controllers/promote_release_controller.py` | controller | ai.presentation.routes | POST /ai/agents/{id}/releases/{rid}/promote | - | low | controller test |
| `src/modules/ai/presentation/controllers/rollback_release_controller.py` | `src/modules/agent/presentation/controllers/rollback_release_controller.py` | controller | ai.presentation.routes | POST /ai/agents/{id}/releases/{rid}/rollback | - | low | controller test |
| `src/modules/ai/presentation/controllers/update_agent_controller.py` | `src/modules/agent/presentation/controllers/update_agent_controller.py` | controller | ai.presentation.routes | PATCH /ai/agents/{id} | - | low | controller test |
| `src/modules/ai/presentation/controllers/update_contract_version_controller.py` | `src/modules/agent/presentation/controllers/update_contract_version_controller.py` | controller | ai.presentation.routes | PATCH /ai/agents/{id}/contracts/{cid} | - | low | controller test |
| `src/modules/ai/presentation/controllers/update_provider_credential_controller.py` | `src/modules/agent/presentation/controllers/update_provider_credential_controller.py` | controller | ai.presentation.routes | PATCH /ai/credentials/{id} | - | low | controller test |

## Database Tables (Schema: ai → agent)

| Table | Current Schema | Target Schema | Model | FKs intra-module | FKs cross-module (blocker) | Risk | Migration spec |
|---|---|---|---|---|---|---|---|
| provider_credentials | ai | agent | ProviderCredentialModel | - | project_id → core.projects.id | medium | 134 |
| agents | ai | agent | AgentModel | provider_credential_id → ai.provider_credentials.id, fallback_credential_id → ai.provider_credentials.id | project_id → core.projects.id | medium | 134 |
| agent_prompts | ai | agent | AgentPromptModel | agent_id → ai.agents.id | project_id → core.projects.id, created_by → identity.users.id | medium | 134 |
| agent_contracts | ai | agent | AgentContractModel | agent_id → ai.agents.id | project_id → core.projects.id | medium | 134 |
| agent_model_configs | ai | agent | AgentModelConfigModel | agent_id → ai.agents.id, provider_credential_id → ai.provider_credentials.id | project_id → core.projects.id | medium | 134 |
| agent_releases | ai | agent | AgentReleaseModel | agent_id → ai.agents.id, prompt_version_id → ai.agent_prompts.id, contract_version_id → ai.agent_contracts.id, model_config_version_id → ai.agent_model_configs.id, provider_credential_id → ai.provider_credentials.id, fallback_credential_id → ai.provider_credentials.id | project_id → core.projects.id, knowledge_version_id → knowledge.knowledge_versions.id, created_by → identity.users.id, promoted_by → identity.users.id | high | 134 |
| agent_release_tests | ai | agent | AgentReleaseTestModel | agent_id → ai.agents.id, release_id → ai.agent_releases.id, contract_version_id → ai.agent_contracts.id | project_id → core.projects.id | medium | 134 |
| outbox_events | ai | agent | OutboxEventModel | - | - | medium — merge with knowledge/runtime outbox | 070-076 |
| inbox_events | ai | agent | InboxEventModel | - | - | medium — merge with knowledge/runtime inbox | 070-076 |

## Events Produced

| event_type | aggregate_type | Producer use case | Current schema | Target schema | Routing impact | Risk |
|---|---|---|---|---|---|---|
| `provider_credential.created` | provider_credential | CreateProviderCredentialUseCase | ai.outbox_events | agent.outbox_events | InboxConsumer routes to "provider_credential" (fails — no such module) | medium — already broken |
| `provider_credential.updated` | provider_credential | UpdateProviderCredentialUseCase | ai.outbox_events | agent.outbox_events | InboxConsumer routes to "provider_credential" (fails) | medium — already broken |
| `agent.created` | agent | CreateAgentUseCase | ai.outbox_events | agent.outbox_events | InboxConsumer routes to "agent" (will work after agent module exists) | low |
| `agent.updated` | agent | UpdateAgentUseCase | ai.outbox_events | agent.outbox_events | InboxConsumer routes to "agent" (will work after agent module exists) | low |

## External Consumers of AI Module

| Consumer file | Import path | Symbols used | Resolution strategy |
|---|---|---|---|
| `src/modules/runtime/service/ask_use_case.py` | `modules.ai.domain.entities` | Agent, AgentRelease, ProviderCredential | Consolidate into agent domain (specs 040-045) |
| `src/modules/runtime/service/ask_use_case.py` | `modules.ai.domain.errors` | AgentNotFoundError, CredentialNotFoundError | Consolidate into agent domain |
| `src/modules/runtime/service/ask_use_case.py` | `modules.ai.domain.repositories` | AgentRepository, AgentReleaseRepository, ProviderCredentialRepository, AgentContractRepository, AgentModelConfigRepository | Consolidate into agent domain |
| `src/modules/runtime/service/ask_use_case.py` | `modules.ai.infra.llm.langchain_factory` | create_chat_model | Consolidate into agent infra |
| `src/modules/runtime/service/ask_use_case.py` | `modules.ai.domain.enums` | Provider (inline) | Consolidate into agent domain |
| `src/modules/runtime/service/ask_agent_stream_service.py` | `modules.ai.domain.entities` | Agent, AgentRelease, ProviderCredential | Consolidate into agent domain |
| `src/modules/runtime/service/ask_agent_stream_service.py` | `modules.ai.domain.errors` | AgentNotFoundError, CredentialNotFoundError | Consolidate into agent domain |
| `src/modules/runtime/service/ask_agent_stream_service.py` | `modules.ai.domain.repositories` | (all 5 repos) | Consolidate into agent domain |
| `src/modules/runtime/service/ask_agent_stream_service.py` | `modules.ai.infra.llm.langchain_factory` | create_chat_model | Consolidate into agent infra |
| `src/modules/runtime/service/ask_agent_stream_service.py` | `modules.ai.infra.repositories` | (all SQLAlchemy repos) | Consolidate into agent infra |
| `src/modules/runtime/infra/ask_job_worker.py` | `modules.ai.infra.repositories` | SQLAlchemyAgentRepository, SQLAlchemyAgentReleaseRepository, SQLAlchemyProviderCredentialRepository, SQLAlchemyAgentContractRepository, SQLAlchemyAgentModelConfigRepository | Consolidate into agent infra |
| `src/modules/runtime/application/composers/ask_agent_composer.py` | `modules.ai.infra.repositories` | (all SQLAlchemy repos) | Consolidate into agent infra |
| `src/main.py` | `modules.ai.presentation.routes` | router (as ai_router) | Update bootstrap to agent (spec 130-131) |
| `migrations/env.py` | `modules.ai.infra.models` | (metadata) | Update to agent (spec 134) |
| `src/shared/workers/outbox_publisher.py` | dynamic: module list includes "ai" | OutboxEventModel | Replace with registry (specs 050-063) |
| `src/shared/workers/inbox_dispatcher.py` | dynamic: module list includes "ai" | InboxEventModel | Replace with registry (specs 050-063) |
| `tests/unit/test_ai/*` | `modules.ai.*` | all test imports | Update to agent after move |
| `tests/helpers.py` | `modules.ai.*` | factory helpers | Update to agent after move |

## Route Migration Plan

| Current route | Target route | Shim required | Shim removal spec |
|---|---|---|---|
| `/ai/credentials` | `/agent/credentials` | yes — redirect/proxy | 140 |
| `/ai/agents` | `/agent/agents` | yes — redirect/proxy | 140 |
| `/ai/agents/{id}` | `/agent/agents/{id}` | yes — redirect/proxy | 140 |
| `/ai/agents/{id}/prompts` | `/agent/agents/{id}/prompts` | yes — redirect/proxy | 140 |
| `/ai/agents/{id}/contracts` | `/agent/agents/{id}/contracts` | yes — redirect/proxy | 140 |
| `/ai/agents/{id}/model-configs` | `/agent/agents/{id}/model-configs` | yes — redirect/proxy | 140 |
| `/ai/agents/{id}/releases` | `/agent/agents/{id}/releases` | yes — redirect/proxy | 140 |
| `/ai/agents/{id}/release-tests` | `/agent/agents/{id}/release-tests` | yes — redirect/proxy | 140 |

## Risk Summary

| Risk | Severity | Mitigation | Responsible spec |
|---|---|---|---|
| runtime imports 28 symbols from ai domain/infra | high | All merge into agent; runtime becomes internal to agent | 040-045 |
| ai.agent_releases FK → knowledge.knowledge_versions.id (cross ai↔knowledge) | medium | Becomes intra-module FK after consolidation into agent | 030-035, 134 |
| Schema rename ai→agent requires expand-migrate-contract | high | Physical schema change deferred to spec 134 | 134 |
| 25 routes under /ai need shim to /agent | medium | Create shim during route migration, remove at spec 140 | 024, 131, 140 |
| shared/workers hard-codes "ai" in module list | medium | Replace with registry pattern | 050-063 |
| 4 ai events have broken inbox routing (no module prefix) | medium (pre-existing) | Fix during event standardization | 100-109 |

## Migration Order

The ai module should be migrated layer by layer per specs 021-025:

1. **Spec 021** — Move ai domain to agent domain (entities, enums, errors, repositories)
2. **Spec 022** — Move ai application to agent application (composers, use cases, DTOs)
3. **Spec 023** — Move ai infra/llm to agent infra/llm (langchain_factory)
4. **Spec 024** — Move ai presentation to agent presentation (routes, schemas, controllers, mappers)
5. **Spec 025** — Update all ai imports to agent imports (shims, tests, bootstrap)

No physical file should be moved until specs 021+ are activated.
