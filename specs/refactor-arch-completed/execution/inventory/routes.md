# API Route Map — ProjectRAI

## Comandos de detecção executados

```
grep "APIRouter|include_router|@router\.(get|post|patch|put|delete)" src/**/*.py
read src/main.py
read src/modules/*/presentation/routes.py
```

## Registro de routers em `src/main.py`

| Ordem | Import | Variável | Prefixo | Módulo |
|---:|---|---|---|---|
| 1 | `modules.identity.presentation.routes` | `identity_router` | `/identity` | identity |
| 2 | `modules.core.presentation.routes` | `core_router` | `/core` | core |
| 3 | `modules.ai.presentation.routes` | `ai_router` | `/ai` | ai (legado → agent) |
| 4 | `modules.knowledge.presentation.routes` | `knowledge_router` | `/knowledge` | knowledge (legado → agent) |
| 5 | `modules.runtime.presentation.routes` | `runtime_router` | `/runtime` | runtime (legado → agent) |
| 6 | `modules.tools.presentation.routes` | `tools_router` | `/tools` | tools |
| 7 | `modules.metering.presentation.routes` | `metering_router` | `/metering` | metering |
| 8 | `modules.billing.presentation.routes` | `billing_router` | `/billing` | billing |
| 9 | `modules.observability.presentation.routes` | `observability_router` | `/observability` | observability |

Rota adicional definida inline em `src/main.py:106`:

| Método | Path | Handler | Módulo |
|---|---|---|---|
| GET | `/health` | `health` (inline) | app |

## Rotas por módulo

### identity — `src/modules/identity/presentation/routes.py`

Prefixo: `/identity` | Tags: `["identity"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| GET | `/identity/organizations` | `list_organizations` | `list_organizations_composer` |
| GET | `/identity/users/me` | `get_current_user` | `get_current_user_composer` |
| POST | `/identity/auth/login` | `login` | `login_composer` |
| POST | `/identity/auth/register` | `register` | `register_composer` |
| POST | `/identity/users` | `create_user` | `create_user_composer` |
| POST | `/identity/organizations` | `create_organization` | `create_organization_composer` |
| POST | `/identity/organizations/{org_id}/members` | `add_member` | `add_member_composer` |
| GET | `/identity/organizations/{org_id}` | `get_organization` | `get_organization_composer` |
| PATCH | `/identity/organizations/{org_id}` | `update_organization` | `update_organization_composer` |
| GET | `/identity/organizations/{org_id}/members` | `list_members` | `list_members_composer` |
| POST | `/identity/organizations/{org_id}/invites` | `create_invite` | `create_invite_composer` |
| GET | `/identity/organizations/{org_id}/invites` | `list_invites` | `list_invites_composer` |
| GET | `/identity/users/{user_id}` | `get_user` | `get_user_composer` |

Total: 13 rotas.

### core — `src/modules/core/presentation/routes.py`

Prefixo: `/core` | Tags: `["core"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| GET | `/core/projects` | `list_projects` | `list_projects_composer` |
| POST | `/core/projects` | `create_project` | `create_project_composer` |
| GET | `/core/projects/{project_id}` | `get_project` | `get_project_composer` |
| PATCH | `/core/projects/{project_id}` | `update_project` | `update_project_composer` |
| POST | `/core/projects/{project_id}/api-keys` | `create_api_key` | `create_api_key_composer` |
| GET | `/core/projects/{project_id}/api-keys` | `list_api_keys` | `list_api_keys_composer` |

Total: 6 rotas.

### ai (legado → agent) — `src/modules/ai/presentation/routes.py`

Prefixo: `/ai` | Tags: `["ai"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| POST | `/ai/credentials` | `create_provider_credential` | `create_provider_credential_composer` |
| PATCH | `/ai/credentials/{credential_id}` | `update_provider_credential` | `update_provider_credential_composer` |
| GET | `/ai/credentials` | `list_provider_credentials` | `list_provider_credentials_composer` |
| POST | `/ai/agents` | `create_agent` | `create_agent_composer` |
| GET | `/ai/agents` | `list_agents` | `list_agents_composer` |
| GET | `/ai/agents/{agent_id}` | `get_agent` | `get_agent_composer` |
| PATCH | `/ai/agents/{agent_id}` | `update_agent` | `update_agent_composer` |
| POST | `/ai/agents/{agent_id}/prompts` | `create_prompt` | `create_prompt_version_composer` |
| GET | `/ai/agents/{agent_id}/prompts` | `list_prompts` | `list_prompt_versions_composer` |
| GET | `/ai/agents/{agent_id}/prompts/{version_id}` | `get_prompt` | `get_prompt_version_composer` |
| POST | `/ai/agents/{agent_id}/contracts` | `create_contract` | `create_contract_version_composer` |
| PATCH | `/ai/agents/{agent_id}/contracts/{contract_id}` | `update_contract` | `update_contract_version_composer` |
| GET | `/ai/agents/{agent_id}/contracts` | `list_contracts` | `list_contract_versions_composer` |
| GET | `/ai/agents/{agent_id}/contracts/{contract_id}` | `get_contract` | `get_contract_version_composer` |
| POST | `/ai/agents/{agent_id}/model-configs` | `create_model_config` | `create_model_config_composer` |
| GET | `/ai/agents/{agent_id}/model-configs` | `list_model_configs` | `list_model_configs_composer` |
| GET | `/ai/agents/{agent_id}/model-configs/{config_id}` | `get_model_config` | `get_model_config_composer` |
| POST | `/ai/agents/{agent_id}/releases` | `create_release` | `create_release_composer` |
| GET | `/ai/agents/{agent_id}/releases` | `list_releases` | `list_releases_composer` |
| GET | `/ai/agents/{agent_id}/releases/{release_id}` | `get_release` | `get_release_composer` |
| POST | `/ai/agents/{agent_id}/releases/{release_id}/promote` | `promote_release` | `promote_release_composer` |
| POST | `/ai/agents/{agent_id}/releases/{release_id}/rollback` | `rollback_release` | `rollback_release_composer` |
| DELETE | `/ai/agents/{agent_id}/releases/{release_id}` | `delete_release` | `delete_release_composer` |
| POST | `/ai/agents/{agent_id}/release-tests` | `create_release_test` | `create_release_test_composer` |
| GET | `/ai/agents/{agent_id}/releases/{release_id}/tests` | `list_release_tests` | `list_release_tests_composer` |

Total: 25 rotas.

### knowledge (legado → agent) — `src/modules/knowledge/presentation/routes.py`

Prefixo: `/knowledge` | Tags: `["knowledge"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| GET | `/knowledge/collections` | `list_collections` | `list_collections_composer` |
| POST | `/knowledge/collections` | `create_collection` | `create_collection_composer` |
| GET | `/knowledge/collections/{collection_id}` | `get_collection` | `get_collection_composer` |
| GET | `/knowledge/agent-collections` | `list_agent_collections` | `list_agent_collections_composer` |
| POST | `/knowledge/agent-collections` | `attach_collection` | `attach_collection_composer` |
| DELETE | `/knowledge/agent-collections/{link_id}` | `detach_collection` | `detach_collection_composer` |
| GET | `/knowledge/documents` | `list_documents` | `list_documents_composer` |
| POST | `/knowledge/documents` | `upload_document` | `upload_document_composer` |
| GET | `/knowledge/documents/{document_id}` | `get_document` | `get_document_composer` |
| POST | `/knowledge/search` | `search_chunks` | `search_chunks_composer` |
| POST | `/knowledge/agents/{agent_id}/knowledge-versions` | `create_knowledge_version` | `create_knowledge_version_composer` |
| GET | `/knowledge/agents/{agent_id}/knowledge-versions` | `list_knowledge_versions` | `list_knowledge_versions_composer` |

Total: 12 rotas.

### runtime (legado → agent) — `src/modules/runtime/presentation/routes.py`

Prefixo: `/runtime` | Tags: `["runtime"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| POST | `/runtime/sessions` | `create_session` | `create_session_composer` |
| GET | `/runtime/agents/{agent_id}/sessions` | `list_agent_sessions` | `list_agent_sessions_composer` |
| POST | `/runtime/ask` | `ask` | `ask_agent_composer` |
| POST | `/runtime/ask/stream` | `ask_stream` | `ask_agent_stream_composer` |
| POST | `/runtime/ask/jobs` | `create_ask_job` | `create_ask_job_composer` |
| GET | `/runtime/ask/jobs/{job_id}` | `get_ask_job` | `get_ask_job_composer` |
| GET | `/runtime/sessions/{session_id}/messages` | `list_messages` | `list_messages_composer` |

Total: 7 rotas.

### tools — `src/modules/tools/presentation/routes.py`

Prefixo: `/tools` | Tags: `["tools"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| GET | `/tools/tools` | `list_tools` | `list_tools_composer` |
| POST | `/tools/tools` | `create_tool` | `create_tool_composer` |
| PATCH | `/tools/tools/{tool_id}` | `update_tool` | `update_tool_composer` |
| PATCH | `/tools/tools/{tool_id}/status` | `update_tool_status` | `update_tool_status_composer` |
| DELETE | `/tools/tools/{tool_id}` | `delete_tool` | `delete_tool_composer` |
| POST | `/tools/tools/test` | `test_tool` | `test_tool_composer` |
| POST | `/tools/tools/execute` | `execute_tool` | `execute_tool_composer` |
| GET | `/tools/agents/{agent_id}/tools` | `list_tools_by_agent` | `list_tools_by_agent_composer` |
| GET | `/tools/secrets` | `list_secrets` | `list_secrets_composer` |
| POST | `/tools/secrets` | `create_secret` | `create_secret_composer` |

Total: 10 rotas.

### metering — `src/modules/metering/presentation/routes.py`

Prefixo: `/metering` | Tags: `["metering"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| POST | `/metering/usage-events` | `record_usage` | `record_usage_composer` |
| GET | `/metering/projects/{project_id}/daily` | `get_project_daily_usage` | `get_project_daily_usage_composer` |
| GET | `/metering/agents/{agent_id}/daily` | `get_agent_daily_usage` | `get_agent_daily_usage_composer` |

Total: 3 rotas.

### billing — `src/modules/billing/presentation/routes.py`

Prefixo: `/billing` | Tags: `["billing"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| POST | `/billing/plans` | `create_plan` | `create_plan_composer` |
| GET | `/billing/plans` | `list_plans` | `list_plans_composer` |
| POST | `/billing/subscriptions` | `create_subscription` | `create_subscription_composer` |
| GET | `/billing/organizations/{org_id}/subscription` | `get_organization_subscription` | `get_organization_subscription_composer` |

Total: 4 rotas.

### observability — `src/modules/observability/presentation/routes.py`

Prefixo: `/observability` | Tags: `["observability"]`

| Método | Path completo | Handler | Composer |
|---|---|---|---|
| GET | `/observability/traces` | `list_traces` | `list_traces_composer` |
| POST | `/observability/traces` | `create_trace` | `create_trace_composer` |
| POST | `/observability/traces/{trace_id}/events` | `add_trace_event` | `add_trace_event_composer` |
| GET | `/observability/traces/{trace_id}` | `get_trace` | `get_trace_composer` |

Total: 4 rotas.

## Resumo total

| Módulo | Prefixo | Total rotas | Classificação migração |
|---|---|---:|---|
| identity | `/identity` | 13 | permanece (módulo independente) |
| core | `/core` | 6 | permanece (módulo independente) |
| ai | `/ai` | 25 | legado → migra para `agent` |
| knowledge | `/knowledge` | 12 | legado → migra para `agent` |
| runtime | `/runtime` | 7 | legado → migra para `agent` |
| tools | `/tools` | 10 | permanece (módulo independente) |
| metering | `/metering` | 3 | permanece (módulo independente) |
| billing | `/billing` | 4 | permanece (módulo independente) |
| observability | `/observability` | 4 | permanece (módulo independente) |
| app (inline) | `/` | 1 | permanece (health check) |
| **Total** | | **85** | |

## Rotas legadas candidatas a migração para `/agent`

Total: 44 rotas (25 ai + 12 knowledge + 7 runtime).

Após migração, o prefixo-alvo será `/agent` conforme ADR 000. As rotas legadas `/ai`, `/knowledge` e `/runtime` necessitarão de shims de compatibilidade (redirect ou proxy temporário) durante a fase de transição.

## Padrão de composição de rotas

Todos os módulos seguem o mesmo padrão:

1. `APIRouter(prefix="/<module>", tags=["<module>"])` define o router.
2. Cada rota chama um `*_composer(session_factory)` que retorna um handler.
3. O handler é executado via `request_adapter(request, handler)` → `response_adapter(response)`.
4. Exceção: `runtime /ask/stream` retorna diretamente do handler sem `response_adapter`.

Fonte: `src/shared/presentation/http/adapter.py`.

## Shims temporários necessários na migração

| Rota legada | Ação durante migração |
|---|---|
| `/ai/*` | Redirect/shim para `/agent/*` equivalente |
| `/knowledge/*` | Redirect/shim para `/agent/*` equivalente |
| `/runtime/*` | Redirect/shim para `/agent/*` equivalente |

Os shims devem ser criados com:
- Deprecation header (`Deprecation: true`, `Sunset: <date>`)
- Testes de compatibilidade que validem ambos os paths
- Spec de remoção explícita (prevista nas specs 140-145)

## Riscos observados

| Risco | Severidade | Evidência |
|---|---|---|
| 44 rotas legadas precisam de shims simultâneos | média | Contagem acima; se removidas sem shim, quebra clientes existentes |
| `/runtime/ask/stream` não segue padrão `response_adapter` | baixa | `src/modules/runtime/presentation/routes.py:39` — retorna diretamente |
| Sub-routers não detectados (nenhum `include_router` dentro de módulos) | informativo | Apenas `src/main.py` registra routers; padrão flat confirmado |
