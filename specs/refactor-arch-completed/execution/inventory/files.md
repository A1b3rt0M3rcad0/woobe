# Inventário de Arquivos do Repositório — Spec 003

Data: 2026-06-13
Branch: `project-rai-playground_specs-refactory`
Comandos executados: `glob src/**/*`, `glob tests/**/*`, `glob migrations/**/*`, `glob specs/**/*`, `git status --short`, `git branch --show-current`

## Backend — `src/`

### `src/` (raiz)

```
src/__init__.py
src/main.py
```

### `src/workers/` (workers globais — legado)

```
src/workers/__init__.py
src/workers/runner.py
src/workers/dispatcher.py
```

Observação: contém lógica de negócio acoplada a módulos concretos. Migração prevista nas specs 050-063.

### `src/shared/` (shared kernel)

#### `src/shared/domain/`

```
src/shared/domain/__init__.py
src/shared/domain/errors.py
src/shared/domain/events.py
src/shared/domain/objects.py
src/shared/domain/time.py
```

#### `src/shared/application/`

```
src/shared/application/__init__.py
src/shared/application/transactional_handler.py
```

#### `src/shared/presentation/`

```
src/shared/presentation/__init__.py
src/shared/presentation/dependencies.py
src/shared/presentation/errors.py
src/shared/presentation/responses.py
src/shared/presentation/interface/__init__.py
src/shared/presentation/interface/controller.py
src/shared/presentation/http/__init__.py
src/shared/presentation/http/adapter.py
src/shared/presentation/http/request.py
src/shared/presentation/http/response.py
src/shared/presentation/http/types.py
```

#### `src/shared/infra/`

```
src/shared/infra/__init__.py
src/shared/infra/crypto.py
src/shared/infra/llm_usage.py
src/shared/infra/rabbitmq.py
src/shared/infra/config/__init__.py
src/shared/infra/config/config.py
src/shared/infra/config/interface/__init__.py
src/shared/infra/config/interface/unit_of_work.py
src/shared/infra/database/__init__.py
src/shared/infra/database/alembic.py
src/shared/infra/database/base.py
src/shared/infra/database/inbox.py
src/shared/infra/database/outbox.py
src/shared/infra/database/postgres_unit_of_work.py
src/shared/infra/database/session.py
src/shared/infra/database/session_manager.py
src/shared/infra/repositories/__init__.py
src/shared/infra/repositories/base_repository.py
```

#### `src/shared/workers/`

```
src/shared/workers/__init__.py
src/shared/workers/base_worker.py
src/shared/workers/inbox_consumer.py
src/shared/workers/inbox_dispatcher.py
src/shared/workers/outbox_publisher.py
```

Observação: `outbox_publisher.py` e `inbox_dispatcher.py` mantêm listas fixas de módulos concretos (`ai`, `knowledge`, `runtime`). `inbox_consumer.py` roteia por segmento do `event_type` e usa queue global `projectrai.inbox`.

### `src/modules/` (bounded contexts)

#### `src/modules/ai/` (Agentes IA, LLM, prompts, releases)

```
src/modules/ai/__init__.py
src/modules/ai/domain/__init__.py
src/modules/ai/domain/entities.py
src/modules/ai/domain/enums.py
src/modules/ai/domain/errors.py
src/modules/ai/domain/repositories.py
src/modules/ai/application/__init__.py
src/modules/ai/application/composers/__init__.py
src/modules/ai/application/composers/create_agent_composer.py
src/modules/ai/application/composers/create_contract_version_composer.py
src/modules/ai/application/composers/create_model_config_composer.py
src/modules/ai/application/composers/create_prompt_version_composer.py
src/modules/ai/application/composers/create_provider_credential_composer.py
src/modules/ai/application/composers/create_release_composer.py
src/modules/ai/application/composers/create_release_test_composer.py
src/modules/ai/application/composers/delete_release_composer.py
src/modules/ai/application/composers/get_agent_composer.py
src/modules/ai/application/composers/get_contract_version_composer.py
src/modules/ai/application/composers/get_model_config_composer.py
src/modules/ai/application/composers/get_prompt_version_composer.py
src/modules/ai/application/composers/get_release_composer.py
src/modules/ai/application/composers/list_agents_composer.py
src/modules/ai/application/composers/list_contract_versions_composer.py
src/modules/ai/application/composers/list_model_configs_composer.py
src/modules/ai/application/composers/list_prompt_versions_composer.py
src/modules/ai/application/composers/list_provider_credentials_composer.py
src/modules/ai/application/composers/list_release_tests_composer.py
src/modules/ai/application/composers/list_releases_composer.py
src/modules/ai/application/composers/promote_release_composer.py
src/modules/ai/application/composers/rollback_release_composer.py
src/modules/ai/application/composers/update_agent_composer.py
src/modules/ai/application/composers/update_contract_version_composer.py
src/modules/ai/application/composers/update_provider_credential_composer.py
src/modules/ai/infra/__init__.py
src/modules/ai/infra/mappers.py
src/modules/ai/infra/models.py
src/modules/ai/infra/repositories.py
src/modules/ai/infra/llm/__init__.py
src/modules/ai/infra/llm/langchain_factory.py
src/modules/ai/presentation/__init__.py
src/modules/ai/presentation/mappers.py
src/modules/ai/presentation/routes.py
src/modules/ai/presentation/schemas.py
src/modules/ai/presentation/controllers/__init__.py
src/modules/ai/presentation/controllers/create_agent_controller.py
src/modules/ai/presentation/controllers/create_contract_version_controller.py
src/modules/ai/presentation/controllers/create_model_config_controller.py
src/modules/ai/presentation/controllers/create_prompt_version_controller.py
src/modules/ai/presentation/controllers/create_provider_credential_controller.py
src/modules/ai/presentation/controllers/create_release_controller.py
src/modules/ai/presentation/controllers/create_release_test_controller.py
src/modules/ai/presentation/controllers/delete_release_controller.py
src/modules/ai/presentation/controllers/get_agent_controller.py
src/modules/ai/presentation/controllers/get_contract_version_controller.py
src/modules/ai/presentation/controllers/get_model_config_controller.py
src/modules/ai/presentation/controllers/get_prompt_version_controller.py
src/modules/ai/presentation/controllers/get_release_controller.py
src/modules/ai/presentation/controllers/list_agents_controller.py
src/modules/ai/presentation/controllers/list_contract_versions_controller.py
src/modules/ai/presentation/controllers/list_model_configs_controller.py
src/modules/ai/presentation/controllers/list_prompt_versions_controller.py
src/modules/ai/presentation/controllers/list_provider_credentials_controller.py
src/modules/ai/presentation/controllers/list_release_tests_controller.py
src/modules/ai/presentation/controllers/list_releases_controller.py
src/modules/ai/presentation/controllers/promote_release_controller.py
src/modules/ai/presentation/controllers/rollback_release_controller.py
src/modules/ai/presentation/controllers/update_agent_controller.py
src/modules/ai/presentation/controllers/update_contract_version_controller.py
src/modules/ai/presentation/controllers/update_provider_credential_controller.py
src/modules/ai/service/__init__.py
src/modules/ai/service/dtos.py
src/modules/ai/service/use_cases.py
```

#### `src/modules/billing/` (Planos, assinaturas)

```
src/modules/billing/__init__.py
src/modules/billing/domain/__init__.py
src/modules/billing/domain/entities.py
src/modules/billing/domain/enums.py
src/modules/billing/domain/errors.py
src/modules/billing/domain/repositories.py
src/modules/billing/application/__init__.py
src/modules/billing/application/composers/__init__.py
src/modules/billing/application/composers/create_plan_composer.py
src/modules/billing/application/composers/create_subscription_composer.py
src/modules/billing/application/composers/get_organization_subscription_composer.py
src/modules/billing/application/composers/list_plans_composer.py
src/modules/billing/infra/__init__.py
src/modules/billing/infra/mappers.py
src/modules/billing/infra/models.py
src/modules/billing/infra/repositories.py
src/modules/billing/presentation/__init__.py
src/modules/billing/presentation/routes.py
src/modules/billing/presentation/schemas.py
src/modules/billing/presentation/controllers/__init__.py
src/modules/billing/presentation/controllers/create_plan_controller.py
src/modules/billing/presentation/controllers/create_subscription_controller.py
src/modules/billing/presentation/controllers/get_organization_subscription_controller.py
src/modules/billing/presentation/controllers/list_plans_controller.py
src/modules/billing/service/__init__.py
src/modules/billing/service/dtos.py
src/modules/billing/service/use_cases.py
```

#### `src/modules/core/` (Projetos, API keys)

```
src/modules/core/__init__.py
src/modules/core/domain/__init__.py
src/modules/core/domain/entities.py
src/modules/core/domain/enums.py
src/modules/core/domain/errors.py
src/modules/core/domain/repositories.py
src/modules/core/application/__init__.py
src/modules/core/application/dependencies.py
src/modules/core/application/composers/__init__.py
src/modules/core/application/composers/create_api_key_composer.py
src/modules/core/application/composers/create_project_composer.py
src/modules/core/application/composers/get_project_composer.py
src/modules/core/application/composers/list_api_keys_composer.py
src/modules/core/application/composers/list_projects_composer.py
src/modules/core/application/composers/update_project_composer.py
src/modules/core/infra/__init__.py
src/modules/core/infra/mappers.py
src/modules/core/infra/models.py
src/modules/core/infra/repositories.py
src/modules/core/presentation/__init__.py
src/modules/core/presentation/mappers.py
src/modules/core/presentation/routes.py
src/modules/core/presentation/schemas.py
src/modules/core/presentation/controllers/__init__.py
src/modules/core/presentation/controllers/create_api_key_controller.py
src/modules/core/presentation/controllers/create_project_controller.py
src/modules/core/presentation/controllers/get_project_controller.py
src/modules/core/presentation/controllers/list_api_keys_controller.py
src/modules/core/presentation/controllers/list_projects_controller.py
src/modules/core/presentation/controllers/update_project_controller.py
src/modules/core/service/__init__.py
src/modules/core/service/dtos.py
src/modules/core/service/use_cases.py
```

#### `src/modules/identity/` (Usuários, organizações, autenticação)

```
src/modules/identity/__init__.py
src/modules/identity/domain/__init__.py
src/modules/identity/domain/entities.py
src/modules/identity/domain/enums.py
src/modules/identity/domain/errors.py
src/modules/identity/domain/repositories.py
src/modules/identity/application/__init__.py
src/modules/identity/application/composers/__init__.py
src/modules/identity/application/composers/add_member_composer.py
src/modules/identity/application/composers/create_invite_composer.py
src/modules/identity/application/composers/create_organization_composer.py
src/modules/identity/application/composers/create_user_composer.py
src/modules/identity/application/composers/get_current_user_composer.py
src/modules/identity/application/composers/get_organization_composer.py
src/modules/identity/application/composers/get_user_composer.py
src/modules/identity/application/composers/list_invites_composer.py
src/modules/identity/application/composers/list_members_composer.py
src/modules/identity/application/composers/list_organizations_composer.py
src/modules/identity/application/composers/login_composer.py
src/modules/identity/application/composers/register_composer.py
src/modules/identity/application/composers/update_organization_composer.py
src/modules/identity/infra/__init__.py
src/modules/identity/infra/mappers.py
src/modules/identity/infra/models.py
src/modules/identity/infra/repositories.py
src/modules/identity/presentation/__init__.py
src/modules/identity/presentation/routes.py
src/modules/identity/presentation/schemas.py
src/modules/identity/presentation/controllers/__init__.py
src/modules/identity/presentation/controllers/add_member_controller.py
src/modules/identity/presentation/controllers/create_invite_controller.py
src/modules/identity/presentation/controllers/create_organization_controller.py
src/modules/identity/presentation/controllers/create_user_controller.py
src/modules/identity/presentation/controllers/get_current_user_controller.py
src/modules/identity/presentation/controllers/get_organization_controller.py
src/modules/identity/presentation/controllers/get_user_controller.py
src/modules/identity/presentation/controllers/list_invites_controller.py
src/modules/identity/presentation/controllers/list_members_controller.py
src/modules/identity/presentation/controllers/list_organizations_controller.py
src/modules/identity/presentation/controllers/login_controller.py
src/modules/identity/presentation/controllers/register_controller.py
src/modules/identity/presentation/controllers/update_organization_controller.py
src/modules/identity/service/__init__.py
src/modules/identity/service/dtos.py
src/modules/identity/service/use_cases.py
```

#### `src/modules/knowledge/` (Bases de conhecimento, coleções, documentos)

```
src/modules/knowledge/__init__.py
src/modules/knowledge/domain/__init__.py
src/modules/knowledge/domain/entities.py
src/modules/knowledge/domain/enums.py
src/modules/knowledge/domain/errors.py
src/modules/knowledge/domain/repositories.py
src/modules/knowledge/application/__init__.py
src/modules/knowledge/application/composers/__init__.py
src/modules/knowledge/application/composers/attach_collection_composer.py
src/modules/knowledge/application/composers/create_collection_composer.py
src/modules/knowledge/application/composers/create_knowledge_version_composer.py
src/modules/knowledge/application/composers/detach_collection_composer.py
src/modules/knowledge/application/composers/get_collection_composer.py
src/modules/knowledge/application/composers/get_document_composer.py
src/modules/knowledge/application/composers/list_agent_collections_composer.py
src/modules/knowledge/application/composers/list_collections_composer.py
src/modules/knowledge/application/composers/list_documents_composer.py
src/modules/knowledge/application/composers/list_knowledge_versions_composer.py
src/modules/knowledge/application/composers/search_chunks_composer.py
src/modules/knowledge/application/composers/upload_document_composer.py
src/modules/knowledge/infra/__init__.py
src/modules/knowledge/infra/mappers.py
src/modules/knowledge/infra/models.py
src/modules/knowledge/infra/repositories.py
src/modules/knowledge/presentation/__init__.py
src/modules/knowledge/presentation/mappers.py
src/modules/knowledge/presentation/routes.py
src/modules/knowledge/presentation/schemas.py
src/modules/knowledge/presentation/controllers/__init__.py
src/modules/knowledge/presentation/controllers/attach_collection_controller.py
src/modules/knowledge/presentation/controllers/create_collection_controller.py
src/modules/knowledge/presentation/controllers/create_knowledge_version_controller.py
src/modules/knowledge/presentation/controllers/detach_collection_controller.py
src/modules/knowledge/presentation/controllers/get_collection_controller.py
src/modules/knowledge/presentation/controllers/get_document_controller.py
src/modules/knowledge/presentation/controllers/list_agent_collections_controller.py
src/modules/knowledge/presentation/controllers/list_collections_controller.py
src/modules/knowledge/presentation/controllers/list_documents_controller.py
src/modules/knowledge/presentation/controllers/list_knowledge_versions_controller.py
src/modules/knowledge/presentation/controllers/search_chunks_controller.py
src/modules/knowledge/presentation/controllers/upload_document_controller.py
src/modules/knowledge/service/__init__.py
src/modules/knowledge/service/dtos.py
src/modules/knowledge/service/use_cases.py
```

#### `src/modules/metering/` (Metrificação de uso)

```
src/modules/metering/__init__.py
src/modules/metering/domain/__init__.py
src/modules/metering/domain/entities.py
src/modules/metering/domain/enums.py
src/modules/metering/domain/errors.py
src/modules/metering/domain/repositories.py
src/modules/metering/application/__init__.py
src/modules/metering/application/composers/__init__.py
src/modules/metering/application/composers/get_agent_daily_usage_composer.py
src/modules/metering/application/composers/get_project_daily_usage_composer.py
src/modules/metering/application/composers/record_usage_composer.py
src/modules/metering/infra/__init__.py
src/modules/metering/infra/mappers.py
src/modules/metering/infra/models.py
src/modules/metering/infra/repositories.py
src/modules/metering/presentation/__init__.py
src/modules/metering/presentation/routes.py
src/modules/metering/presentation/schemas.py
src/modules/metering/presentation/controllers/__init__.py
src/modules/metering/presentation/controllers/get_agent_daily_usage_controller.py
src/modules/metering/presentation/controllers/get_project_daily_usage_controller.py
src/modules/metering/presentation/controllers/record_usage_controller.py
src/modules/metering/service/__init__.py
src/modules/metering/service/dtos.py
src/modules/metering/service/use_cases.py
```

#### `src/modules/observability/` (Traces, eventos)

```
src/modules/observability/__init__.py
src/modules/observability/domain/__init__.py
src/modules/observability/domain/entities.py
src/modules/observability/domain/enums.py
src/modules/observability/domain/errors.py
src/modules/observability/domain/repositories.py
src/modules/observability/application/__init__.py
src/modules/observability/application/composers/__init__.py
src/modules/observability/application/composers/add_trace_event_composer.py
src/modules/observability/application/composers/create_trace_composer.py
src/modules/observability/application/composers/get_trace_composer.py
src/modules/observability/application/composers/list_traces_composer.py
src/modules/observability/infra/__init__.py
src/modules/observability/infra/mappers.py
src/modules/observability/infra/models.py
src/modules/observability/infra/repositories.py
src/modules/observability/presentation/__init__.py
src/modules/observability/presentation/routes.py
src/modules/observability/presentation/schemas.py
src/modules/observability/presentation/controllers/__init__.py
src/modules/observability/presentation/controllers/add_trace_event_controller.py
src/modules/observability/presentation/controllers/create_trace_controller.py
src/modules/observability/presentation/controllers/get_trace_controller.py
src/modules/observability/presentation/controllers/list_traces_controller.py
src/modules/observability/service/__init__.py
src/modules/observability/service/dtos.py
src/modules/observability/service/use_cases.py
```

#### `src/modules/runtime/` (Sessões, mensagens, ask agent)

```
src/modules/runtime/__init__.py
src/modules/runtime/domain/__init__.py
src/modules/runtime/domain/entities.py
src/modules/runtime/domain/enums.py
src/modules/runtime/domain/errors.py
src/modules/runtime/domain/repositories.py
src/modules/runtime/application/__init__.py
src/modules/runtime/application/composers/__init__.py
src/modules/runtime/application/composers/ask_agent_composer.py
src/modules/runtime/application/composers/ask_agent_stream_composer.py
src/modules/runtime/application/composers/create_ask_job_composer.py
src/modules/runtime/application/composers/create_session_composer.py
src/modules/runtime/application/composers/get_ask_job_composer.py
src/modules/runtime/application/composers/list_agent_sessions_composer.py
src/modules/runtime/application/composers/list_messages_composer.py
src/modules/runtime/application/composers/send_message_composer.py
src/modules/runtime/infra/__init__.py
src/modules/runtime/infra/ask_job_worker.py
src/modules/runtime/infra/mappers.py
src/modules/runtime/infra/models.py
src/modules/runtime/infra/repositories.py
src/modules/runtime/presentation/__init__.py
src/modules/runtime/presentation/routes.py
src/modules/runtime/presentation/schemas.py
src/modules/runtime/presentation/controllers/__init__.py
src/modules/runtime/presentation/controllers/ask_agent_controller.py
src/modules/runtime/presentation/controllers/ask_agent_stream_controller.py
src/modules/runtime/presentation/controllers/create_ask_job_controller.py
src/modules/runtime/presentation/controllers/create_session_controller.py
src/modules/runtime/presentation/controllers/get_ask_job_controller.py
src/modules/runtime/presentation/controllers/list_agent_sessions_controller.py
src/modules/runtime/presentation/controllers/list_messages_controller.py
src/modules/runtime/presentation/controllers/send_message_controller.py
src/modules/runtime/service/__init__.py
src/modules/runtime/service/ask_agent_stream_service.py
src/modules/runtime/service/ask_use_case.py
src/modules/runtime/service/dtos.py
src/modules/runtime/service/use_cases.py
```

Observação: `ask_job_worker.py` monta UoW com repositories de múltiplos módulos. `ask_use_case.py` importa domínio/repositórios de `ai`, `knowledge`, `metering` e `observability` diretamente.

#### `src/modules/tools/` (Ferramentas, secrets, execução)

```
src/modules/tools/__init__.py
src/modules/tools/domain/__init__.py
src/modules/tools/domain/entities.py
src/modules/tools/domain/enums.py
src/modules/tools/domain/errors.py
src/modules/tools/domain/repositories.py
src/modules/tools/application/__init__.py
src/modules/tools/application/providers.py
src/modules/tools/application/composers/__init__.py
src/modules/tools/application/composers/create_secret_composer.py
src/modules/tools/application/composers/create_tool_composer.py
src/modules/tools/application/composers/delete_tool_composer.py
src/modules/tools/application/composers/execute_tool_composer.py
src/modules/tools/application/composers/list_secrets_composer.py
src/modules/tools/application/composers/list_tools_by_agent_composer.py
src/modules/tools/application/composers/list_tools_composer.py
src/modules/tools/application/composers/test_tool_composer.py
src/modules/tools/application/composers/update_tool_composer.py
src/modules/tools/application/composers/update_tool_status_composer.py
src/modules/tools/infra/__init__.py
src/modules/tools/infra/mappers.py
src/modules/tools/infra/models.py
src/modules/tools/infra/repositories.py
src/modules/tools/presentation/__init__.py
src/modules/tools/presentation/routes.py
src/modules/tools/presentation/schemas.py
src/modules/tools/presentation/controllers/__init__.py
src/modules/tools/presentation/controllers/create_secret_controller.py
src/modules/tools/presentation/controllers/create_tool_controller.py
src/modules/tools/presentation/controllers/delete_tool_controller.py
src/modules/tools/presentation/controllers/execute_tool_controller.py
src/modules/tools/presentation/controllers/list_secrets_controller.py
src/modules/tools/presentation/controllers/list_tools_by_agent_controller.py
src/modules/tools/presentation/controllers/list_tools_controller.py
src/modules/tools/presentation/controllers/test_tool_controller.py
src/modules/tools/presentation/controllers/update_tool_controller.py
src/modules/tools/presentation/controllers/update_tool_status_controller.py
src/modules/tools/service/__init__.py
src/modules/tools/service/dtos.py
src/modules/tools/service/tool_converter.py
src/modules/tools/service/use_cases.py
```

#### `src/modules/agent/` — NÃO EXISTE

O diretório `src/modules/agent/` ainda não foi criado. A migração de `ai`, `knowledge` e `runtime` para este bounded context é o objetivo das specs 010-045.

---

## Tests — `tests/`

```
tests/__init__.py
tests/conftest.py
tests/helpers.py
tests/e2e/__init__.py
tests/integration/__init__.py
tests/unit/__init__.py
tests/unit/test_ai/test_dtos.py
tests/unit/test_ai/test_entities.py
tests/unit/test_ai/test_enums.py
tests/unit/test_ai/test_errors.py
tests/unit/test_ai/test_use_cases.py
tests/unit/test_billing/__init__.py
tests/unit/test_billing/test_dtos.py
tests/unit/test_billing/test_entities.py
tests/unit/test_billing/test_enums.py
tests/unit/test_billing/test_errors.py
tests/unit/test_billing/test_use_cases.py
tests/unit/test_core/test_dtos.py
tests/unit/test_core/test_entities.py
tests/unit/test_core/test_enums.py
tests/unit/test_core/test_errors.py
tests/unit/test_core/test_use_cases.py
tests/unit/test_identity/test_dtos.py
tests/unit/test_identity/test_entities.py
tests/unit/test_identity/test_enums.py
tests/unit/test_identity/test_errors.py
tests/unit/test_identity/test_use_cases.py
tests/unit/test_knowledge/__init__.py
tests/unit/test_knowledge/test_dtos.py
tests/unit/test_knowledge/test_entities.py
tests/unit/test_knowledge/test_enums.py
tests/unit/test_knowledge/test_errors.py
tests/unit/test_knowledge/test_use_cases.py
tests/unit/test_metering/__init__.py
tests/unit/test_metering/test_dtos.py
tests/unit/test_metering/test_entities.py
tests/unit/test_metering/test_enums.py
tests/unit/test_metering/test_errors.py
tests/unit/test_metering/test_use_cases.py
tests/unit/test_observability/__init__.py
tests/unit/test_observability/test_dtos.py
tests/unit/test_observability/test_entities.py
tests/unit/test_observability/test_enums.py
tests/unit/test_observability/test_errors.py
tests/unit/test_observability/test_use_cases.py
tests/unit/test_runtime/__init__.py
tests/unit/test_runtime/test_dtos.py
tests/unit/test_runtime/test_entities.py
tests/unit/test_runtime/test_enums.py
tests/unit/test_runtime/test_errors.py
tests/unit/test_runtime/test_use_cases.py
tests/unit/test_shared/__init__.py
tests/unit/test_shared/test_crypto.py
tests/unit/test_shared/test_errors.py
tests/unit/test_shared/test_llm_usage.py
tests/unit/test_shared/test_objects.py
tests/unit/test_tools/__init__.py
tests/unit/test_tools/test_dtos.py
tests/unit/test_tools/test_entities.py
tests/unit/test_tools/test_enums.py
tests/unit/test_tools/test_errors.py
tests/unit/test_tools/test_use_cases.py
tests/architecture/__init__.py
tests/architecture/test_agent_target_directory_structure.py
tests/architecture/test_architecture_decision_record_agent_bounded_context.py
tests/architecture/test_architecture_rules_modular_monolith_boundaries.py
```

Observação: `tests/unit/test_core/` e `tests/unit/test_identity/` não possuem `__init__.py`, causando erros de coleção pré-existentes no pytest.

---

## Migrations — `migrations/`

```
migrations/__init__.py
migrations/env.py
migrations/script.py.mako
migrations/versions/__init__.py
migrations/versions/0001_create_schemas.py
migrations/versions/0002_create_all_tables.py
migrations/versions/0003_add_metadata_to_provider_credentials.py
migrations/versions/0004_add_mode_to_sessions.py
migrations/versions/0005_fix_datetime_timezones.py
migrations/versions/0006_add_ask_jobs_table.py
migrations/versions/0007_create_agent_versioning_tables.py
migrations/versions/0008_add_release_snapshot_fields.py
migrations/versions/0009_add_agent_release_missing_fields.py
migrations/versions/0010_add_production_unique_constraint.py
migrations/versions/0011_add_fallback_fields_to_agent_releases.py
migrations/versions/0012_make_tool_agent_id_nullable.py
```

Observação: `migrations/env.py` importa models de `ai`, `knowledge` e `runtime` para metadata do Alembic. 12 migrações versionadas.

---

## Frontend — `web/`

```
web/.env.example
web/Dockerfile
web/index.html
web/package.json
web/package-lock.json
web/postcss.config.js
web/tailwind.config.ts
web/tsconfig.json
web/tsconfig.node.json
web/vite.config.ts
web/README.md
web/src/App.tsx
web/src/index.css
web/src/main.tsx
web/src/vite-env.d.ts
web/src/app/providers.tsx
web/src/app/router.tsx
web/src/layouts/AuthLayout.tsx
web/src/layouts/DashboardLayout.tsx
web/src/layouts/PublicLayout.tsx
web/src/lib/json-utils.ts
web/src/lib/parse-assistant-message.ts
web/src/lib/utils.ts
web/src/lib/api/client.ts
web/src/lib/api/errors.ts
web/src/lib/auth/token.ts
web/src/lib/constants/routes.ts
web/src/lib/formatters/bytes.ts
web/src/lib/formatters/date.ts
web/src/lib/formatters/money.ts
web/src/lib/formatters/number.ts
web/src/components/ (UI, common, layout, marketing — ~30 arquivos)
web/src/features/ (agents, api-keys, auth, billing, knowledge, organizations, playground, projects, provider-credentials, tools, traces, usage, workspace)
web/src/pages/ (~23 páginas React)
```

Tecnologia: Vite + React + TypeScript + Tailwind CSS.

---

## Scripts — `scripts/`

```
scripts/__init__.py
scripts/check_dataclass_order.py
scripts/docker-entrypoint.sh
scripts/rename_metadata.py
scripts/run_migrations.py
scripts/seed_customer.py
```

---

## Configuração raiz

```
.alembic.ini
.dockerignore
.env
.env.example
.gitignore
.python-version
Dockerfile
docker-compose.yml
main.py
opencode.json
pyproject.toml
README.md
uv.lock
```

---

## Specs — `specs/`

```
specs/README.md
specs/MANIFEST.md
specs/execution/runtime.md
specs/execution/inventory/.gitkeep
specs/000-architecture-decision-record-agent-bounded-context.md
specs/001-architecture-rules-modular-monolith-boundaries.md
specs/002-agent-target-directory-structure.md
specs/003-create-current-repository-inventory.md
specs/004-create-current-import-dependency-map.md
specs/005-create-current-database-ownership-map.md
specs/006-create-current-api-route-map.md
specs/007-create-current-event-catalog.md
specs/008-create-current-worker-inventory.md
specs/009-create-migration-risk-register.md
specs/010-create-agent-module-skeleton.md ... specs/154-final-migration-report.md
```

Total: 108 arquivos de spec + 2 controle (README, MANIFEST) + 2 execução (runtime.md, inventory/.gitkeep).

---

## Resumo quantitativo

| Categoria | Contagem |
|---|---|
| Arquivos Python backend (`src/`) | ~256 |
| Arquivos de teste (`tests/`) | ~66 |
| Migrações Alembic | 12 versões |
| Configuração raiz | 13 arquivos |
| Specs | 108 documentos |
| Frontend (`web/src/`) | ~120 arquivos TS/TSX |
| Scripts | 6 arquivos |

## Módulos existentes

| Módulo | Camadas | Status na migração |
|---|---|---|
| `ai` | domain, application/composers, infra, infra/llm, presentation/controllers, service | legado → será migrado para `agent` |
| `billing` | domain, application/composers, infra, presentation/controllers, service | permanece independente |
| `core` | domain, application/composers, infra, presentation/controllers, service | permanece independente |
| `identity` | domain, application/composers, infra, presentation/controllers, service | permanece independente |
| `knowledge` | domain, application/composers, infra, presentation/controllers, service | legado → será migrado para `agent` |
| `metering` | domain, application/composers, infra, presentation/controllers, service | permanece independente |
| `observability` | domain, application/composers, infra, presentation/controllers, service | permanece independente |
| `runtime` | domain, application/composers, infra, presentation/controllers, service | legado → será migrado para `agent` |
| `tools` | domain, application/composers, infra, presentation/controllers, service | permanece independente |
| `agent` | — | NÃO EXISTE AINDA |

## Arquivos ausentes esperados

| Arquivo esperado | Status |
|---|---|
| `src/modules/agent/` | não existe — será criado na spec 010 |
| `tests/unit/test_core/__init__.py` | ausente (causa erro de coleção no pytest) |
| `tests/unit/test_identity/__init__.py` | ausente (causa erro de coleção no pytest) |
| `tests/unit/test_ai/__init__.py` | ausente (causa erro de coleção no pytest) |
| `tests/integration/` (testes concretos) | apenas `__init__.py` — sem testes de integração implementados |
| `tests/e2e/` (testes concretos) | apenas `__init__.py` — sem testes e2e implementados |
