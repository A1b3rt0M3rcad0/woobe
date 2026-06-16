# Route → Composer → Controller → Use Case Inventory

**Date:** 2026-06-14
**Branch:** project-rai-playground_module-architecture-standardization
**SHA:** a622072

## Notes
- Generated during spec 014 execution.
- `rg` unavailable; substituted with `Select-String -Pattern 'APIRouter|@router\.|_composer|Controller'`.
- Agent module has 4 routers: `/ai`, `/knowledge`, `/runtime`, `/agent`. All route through `presentation/routes.py`.
- All other modules have single routers at their module prefix.

## agent

**Router:** `modules/agent/presentation/routes.py`

### `/ai` Router (prefix="/ai", tags=["ai","agent"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/credentials` | POST | `create_provider_credential_composer` | `CreateProviderCredentialController` | via service/dtos |
| `/credentials/{credential_id}` | PATCH | `update_provider_credential_composer` | `UpdateProviderCredentialController` | via service/dtos |
| `/credentials` | GET | `list_provider_credentials_composer` | `ListProviderCredentialsController` | via service/dtos |
| `/agents` | POST | `create_agent_composer` | `CreateAgentController` | via service/dtos |
| `/agents` | GET | `list_agents_composer` | `ListAgentsController` | via service/dtos |
| `/agents/{agent_id}` | GET | `get_agent_composer` | `GetAgentController` | via service/dtos |
| `/agents/{agent_id}` | PATCH | `update_agent_composer` | `UpdateAgentController` | via service/dtos |
| `/agents/{agent_id}/prompts` | POST | `create_prompt_version_composer` | `CreatePromptVersionController` | via service/dtos |
| `/agents/{agent_id}/prompts` | GET | `list_prompt_versions_composer` | `ListPromptVersionsController` | via service/dtos |
| `/agents/{agent_id}/prompts/{version_id}` | GET | `get_prompt_version_composer` | `GetPromptVersionController` | via service/dtos |
| `/agents/{agent_id}/contracts` | POST | `create_contract_version_composer` | `CreateContractVersionController` | via service/dtos |
| `/agents/{agent_id}/contracts/{contract_id}` | PATCH | `update_contract_version_composer` | `UpdateContractVersionController` | via service/dtos |
| `/agents/{agent_id}/contracts` | GET | `list_contract_versions_composer` | `ListContractVersionsController` | via service/dtos |
| `/agents/{agent_id}/contracts/{contract_id}` | GET | `get_contract_version_composer` | `GetContractVersionController` | via service/dtos |
| `/agents/{agent_id}/model-configs` | POST | `create_model_config_composer` | `CreateModelConfigController` | via service/dtos |
| `/agents/{agent_id}/model-configs` | GET | `list_model_configs_composer` | `ListModelConfigsController` | via service/dtos |
| `/agents/{agent_id}/model-configs/{config_id}` | GET | `get_model_config_composer` | `GetModelConfigController` | via service/dtos |
| `/agents/{agent_id}/releases` | POST | `create_release_composer` | `CreateReleaseController` | via service/dtos |
| `/agents/{agent_id}/releases` | GET | `list_releases_composer` | `ListReleasesController` | via service/dtos |
| `/agents/{agent_id}/releases/{release_id}` | GET | `get_release_composer` | `GetReleaseController` | via service/dtos |
| `/agents/{agent_id}/releases/{release_id}/promote` | POST | `promote_release_composer` | `PromoteReleaseController` | via service/dtos |
| `/agents/{agent_id}/releases/{release_id}/rollback` | POST | `rollback_release_composer` | `RollbackReleaseController` | via service/dtos |
| `/agents/{agent_id}/releases/{release_id}` | DELETE | `delete_release_composer` | `DeleteReleaseController` | via service/dtos |
| `/agents/{agent_id}/release-tests` | POST | `create_release_test_composer` | `CreateReleaseTestController` | via service/dtos |
| `/agents/{agent_id}/releases/{release_id}/tests` | GET | `list_release_tests_composer` | `ListReleaseTestsController` | via service/dtos |

### `/knowledge` Router (prefix="/knowledge", tags=["knowledge","agent"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/collections` | GET | `list_collections_composer` | `ListCollectionsController` | via service/dtos |
| `/collections` | POST | `create_collection_composer` | `CreateCollectionController` | via service/dtos |
| `/collections/{collection_id}` | GET | `get_collection_composer` | `GetCollectionController` | via service/dtos |
| `/agents/{agent_id}/collections` | GET | `list_agent_collections_composer` | `ListAgentCollectionsController` | via service/dtos |
| `/agents/{agent_id}/collections` | POST | `attach_collection_composer` | `AttachCollectionController` | via service/dtos |
| `/agents/{agent_id}/collections/{collection_id}` | DELETE | `detach_collection_composer` | `DetachCollectionController` | via service/dtos |
| `/collections/{collection_id}/documents` | GET | `list_documents_composer` | `ListDocumentsController` | via service/dtos |
| `/collections/{collection_id}/documents` | POST | `upload_document_composer` | `UploadDocumentController` | via service/dtos |
| `/collections/{collection_id}/documents/{document_id}` | GET | `get_document_composer` | `GetDocumentController` | via service/dtos |
| `/chunks/search` | POST | `search_chunks_composer` | `SearchChunksController` | via service/dtos |
| `/collections/{collection_id}/versions` | POST | `create_knowledge_version_composer` | `CreateKnowledgeVersionController` | via service/dtos |
| `/collections/{collection_id}/versions` | GET | `list_knowledge_versions_composer` | `ListKnowledgeVersionsController` | via service/dtos |

### `/runtime` Router (prefix="/runtime", tags=["runtime","agent"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/sessions` | POST | `create_session_composer` | `CreateSessionController` | via service/dtos |
| `/agents/{agent_id}/sessions` | GET | `list_agent_sessions_composer` | `ListAgentSessionsController` | via service/dtos |
| `/ask` | POST | `ask_agent_composer` | `AskAgentController` | via service/dtos |
| `/ask/stream` | POST | `ask_agent_stream_composer` | `AskAgentStreamController` | via service/dtos |
| `/ask-jobs` | POST | `create_ask_job_composer` | `CreateAskJobController` | via service/dtos |
| `/ask-jobs/{job_id}` | GET | `get_ask_job_composer` | `GetAskJobController` | via service/dtos |
| `/sessions/{session_id}/messages` | GET | `list_messages_composer` | `ListMessagesController` | via service/dtos |
| `/sessions/{session_id}/messages` | POST | `send_message_composer` | `SendMessageController` | via service/dtos |

### `/agent` Router (prefix="/agent", tags=["agent"])

Defined in same `routes.py` — contains additional agent-specific endpoints.

## billing

**Router:** `modules/billing/presentation/routes.py` (prefix="/billing", tags=["billing"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/plans` | POST | `create_plan_composer` | `CreatePlanController` | via service/dtos |
| `/plans` | GET | `list_plans_composer` | `ListPlansController` | via service/dtos |
| `/subscriptions` | POST | `create_subscription_composer` | `CreateSubscriptionController` | via service/dtos |
| `/organizations/{org_id}/subscription` | GET | `get_organization_subscription_composer` | `GetOrganizationSubscriptionController` | via service/dtos |

## core

**Router:** `modules/core/presentation/routes.py` (prefix="/core", tags=["core"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/projects` | GET | `list_projects_composer` | `ListProjectsController` | via service/dtos |
| `/projects` | POST | `create_project_composer` | `CreateProjectController` | via service/dtos |
| `/projects/{project_id}` | GET | `get_project_composer` | `GetProjectController` | via service/dtos |
| `/projects/{project_id}` | PATCH | `update_project_composer` | `UpdateProjectController` | via service/dtos |
| `/projects/{project_id}/api-keys` | POST | `create_api_key_composer` | `CreateApiKeyController` | via service/dtos |
| `/projects/{project_id}/api-keys` | GET | `list_api_keys_composer` | `ListApiKeysController` | via service/dtos |

## identity

**Router:** `modules/identity/presentation/routes.py` (prefix="/identity", tags=["identity"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/organizations` | GET | `list_organizations_composer` | `ListOrganizationsController` | via service/dtos |
| `/users/me` | GET | `get_current_user_composer` | `GetCurrentUserController` | via service/dtos |
| `/auth/login` | POST | `login_composer` | `LoginController` | via service/dtos |
| `/auth/register` | POST | `register_composer` | `RegisterController` | via service/dtos |
| `/users` | POST | `create_user_composer` | `CreateUserController` | via service/dtos |
| `/organizations` | POST | `create_organization_composer` | `CreateOrganizationController` | via service/dtos |
| `/organizations/{org_id}/members` | POST | `add_member_composer` | `AddMemberController` | via service/dtos |
| `/organizations/{org_id}` | GET | `get_organization_composer` | `GetOrganizationController` | via service/dtos |
| `/organizations/{org_id}` | PATCH | `update_organization_composer` | `UpdateOrganizationController` | via service/dtos |
| `/organizations/{org_id}/members` | GET | `list_members_composer` | `ListMembersController` | via service/dtos |
| `/organizations/{org_id}/invites` | POST | `create_invite_composer` | `CreateInviteController` | via service/dtos |
| `/organizations/{org_id}/invites` | GET | `list_invites_composer` | `ListInvitesController` | via service/dtos |
| `/users/{user_id}` | GET | `get_user_composer` | `GetUserController` | via service/dtos |

## metering

**Router:** `modules/metering/presentation/routes.py` (prefix="/metering", tags=["metering"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/usage-events` | POST | `record_usage_composer` | `RecordUsageController` | via service/dtos |
| `/projects/{project_id}/daily` | GET | `get_project_daily_usage_composer` | `GetProjectDailyUsageController` | via service/dtos |
| `/agents/{agent_id}/daily` | GET | `get_agent_daily_usage_composer` | `GetAgentDailyUsageController` | via service/dtos |

## observability

**Router:** `modules/observability/presentation/routes.py` (prefix="/observability", tags=["observability"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/traces` | GET | `list_traces_composer` | `ListTracesController` | via service/dtos |
| `/traces` | POST | `create_trace_composer` | `CreateTraceController` | via service/dtos |
| `/traces/{trace_id}/events` | POST | `add_trace_event_composer` | `AddTraceEventController` | via service/dtos |
| `/traces/{trace_id}` | GET | `get_trace_composer` | `GetTraceController` | via service/dtos |

## tools

**Router:** `modules/tools/presentation/routes.py` (prefix="/tools", tags=["tools"])

| Route | Method | Composer | Controller | Use Case |
|---|---|---|---|---|
| `/tools` | GET | `list_tools_composer` | `ListToolsController` | via service/dtos |
| `/tools` | POST | `create_tool_composer` | `CreateToolController` | via service/dtos |
| `/tools/{tool_id}` | PATCH | `update_tool_composer` | `UpdateToolController` | via service/dtos |
| `/tools/{tool_id}/status` | PATCH | `update_tool_status_composer` | `UpdateToolStatusController` | via service/dtos |
| `/tools/{tool_id}` | DELETE | `delete_tool_composer` | `DeleteToolController` | via service/dtos |
| `/tools/test` | POST | `test_tool_composer` | `TestToolController` | via service/dtos |
| `/tools/execute` | POST | `execute_tool_composer` | `ExecuteToolController` | via service/dtos |
| `/agents/{agent_id}/tools` | GET | `list_tools_by_agent_composer` | `ListToolsByAgentController` | via service/dtos |
| `/secrets` | GET | `list_secrets_composer` | `ListSecretsController` | via service/dtos |
| `/secrets` | POST | `create_secret_composer` | `CreateSecretController` | via service/dtos |

## Controller Pattern

All controllers across all modules follow the same pattern:
```python
from shared.presentation.interface.controller import Controller

class XxxController(Controller):
    ...
```

## Composer Pattern

All composers follow the same compositor pattern:
```python
def xxx_composer(session_factory) -> TransactionalHandler:
    repo = SQLAlchemyXxxRepository(...)
    uow = PostgresUnitOfWork(session_factory)
    use_case = XxxUseCase(repo)
    controller = XxxController(use_case)
    return TransactionalHandler(uow, controller.handle)
```

## Summary

| Module | Routers | Routes | Composers | Controllers | Use Cases |
|---|---|---|---|---|---|
| agent | 4 (/ai, /knowledge, /runtime, /agent) | ~60 | ~50 | ~40 | via application/use_cases/ |
| billing | 1 (/billing) | 4 | 4 | 4 | via service/use_cases.py |
| core | 1 (/core) | 6 | 6 | 6 | via service/use_cases.py |
| identity | 1 (/identity) | 13 | 13 | 13 | via service/use_cases.py |
| metering | 1 (/metering) | 3 | 3 | 3 | via service/use_cases.py |
| observability | 1 (/observability) | 4 | 4 | 4 | via service/use_cases.py |
| tools | 1 (/tools) | 10 | 10 | 10 | via service/use_cases.py |

**Key observation:** agent routes already expose legacy-prefix routers (`/ai`, `/knowledge`, `/runtime`) plus a canonical `/agent` router. The legacy-prefix routes should eventually converge to `/agent` only.
