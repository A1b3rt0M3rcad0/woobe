# Plano de Criação do ProjectRAI — Fases 1-4

## Arquitetura Final

- **9 módulos de negócio:** identity, core, ai, knowledge, runtime, tools, metering, billing, observability
- **Cada módulo possui** seu próprio outbox_events e inbox_events no seu schema
- **Sem módulo events separado** — a infraestrutura abstrata fica em `shared/`

## Estrutura Final

```
src/
  main.py
  shared/
    domain/          # CursorPage, HttpRequest, HttpResponse, DomainError, enums
    application/     # paginação genérica, DTOs base
    infra/
      database/      # Base, BaseModel, session, SessionManager
      repositories/  # BaseRepository
      events/        # OutboxEventModel abstrato, InboxEventModel abstrato
    presentation/    # dependencies comuns, error handlers, responses
    workers/         # BaseWorker
  modules/
    identity/        # users, organizations, members, invites, sessions
    core/            # projects, api_keys
    ai/              # agents, provider_credentials
    knowledge/       # collections, documents, chunks
    runtime/         # sessions, messages
    tools/           # tools, secrets
    metering/        # usage_events, daily aggregates
    billing/         # plans, customers, subscriptions, payments
    observability/   # traces, trace_events
  workers/           # workers concretos
```

> Nota: cada módulo tem `outbox_events` e `inbox_events` no seu schema.

---

## Fase 1 — Esqueleto (concluído)

- Estrutura de diretórios criada
- `__init__.py` com docstrings
- `src/main.py` básico

## Fase 2 — Camada Shared

### `shared/infra/database/base.py`
- `Base(DeclarativeBase)` — base SQLAlchemy
- `BaseModel(Base)` — abstrato com `id` (UUIDv7), `created_at`, `updated_at`

### `shared/infra/database/session.py`
- `create_async_engine`, `async_session_factory`
- Config a partir de settings

### `shared/infra/database/session_manager.py`
- `SessionManager` — async context manager
- `__aenter__` cria session
- `__aexit__` commit ou rollback + close

### `shared/infra/database/outbox.py`
- `OutboxEventModel(BaseModel)` — **abstract**, campos comuns de outbox
  - aggregate_type, aggregate_id, event_type, event_version, payload (JSONB)
  - status (pending/publishing/published/failed/dead)
  - attempts, available_at, published_at, error
  - correlation_id, causation_id

### `shared/infra/database/inbox.py`
- `InboxEventModel(BaseModel)` — **abstract**, campos comuns de inbox
  - outbox_origin_id, aggregate_type, event_type, event_version, payload (JSONB)
  - status (pending/processing/processed/failed/dead)
  - attempts, available_at, processed_at, error
  - consumer_name, correlation_id, causation_id

### `shared/infra/repositories/base_repository.py`
- `BaseRepository[T]` — genérico com CRUD básico
- `add`, `get`, `list`, `update`, `delete`

### `shared/domain/objects.py`
- `CursorPage[T]` — paginação cursor-based
- `HttpRequest`, `HttpResponse`

### `shared/domain/errors.py`
- `DomainError` — base para erros de domínio
- `NotFoundException`, `ConflictError`, `ValidationError`

### `shared/infra/config.py`
- `Settings` via pydantic-settings
- DATABASE_URL, etc.

### `shared/infra/crypto.py`
- `hash_password`, `verify_password`, `encrypt_secret`, `decrypt_secret`

### `shared/presentation/dependencies.py`
- Dependências FastAPI comuns (database session, etc.)

### `shared/presentation/responses.py`
- Helpers de resposta padronizada

### `shared/workers/base_worker.py`
- `BaseWorker` — classe base para workers

## Fase 3 — Models SQLAlchemy (por módulo)

Cada módulo terá em `infra/models.py`:
- Models de negócio do módulo
- `OutboxEventModel` concreto (herdando do abstrato, apontando para schema do módulo)
- `InboxEventModel` concreto (herdando do abstrato, apontando para schema do módulo)

### identity (schema: identity)
- `UserModel` — id, email, password, status, created_at, updated_at
- `OrganizationModel` — id, name, slug, status, created_at, updated_at
- `OrganizationMemberModel` — id, user_id, organization_id, role, status, joined_at
- `OrganizationInviteModel` — id, organization_id, email, role, token_hash, invited_by, status, expires_at
- `UserSessionModel` — id, user_id, refresh_token_hash, user_agent, ip_address, revoked_at, expires_at
- `OutboxEventModel` — schema: identity
- `InboxEventModel` — schema: identity

### core (schema: core)
- `ProjectModel` — id, organization_id, name, slug, status, metadata
- `ApiKeyModel` — id, project_id, name, key_prefix, key_hash, scopes, status, last_used_at, expires_at, revoked_at, created_by
- `OutboxEventModel`, `InboxEventModel` — schema: core

### ai (schema: ai)
- `ProviderCredentialModel` — id, project_id, provider, name, encrypted_secret, status, last_validated_at
- `AgentModel` — id, project_id, provider_credential_id, fallback_credential_id, name, description, type, system_prompt, provider, model, fallback_provider, fallback_model, temperature, max_output_tokens, session_mode, status, settings
- `OutboxEventModel`, `InboxEventModel` — schema: ai

### knowledge (schema: knowledge)
- `DocumentCollectionModel` — id, project_id, name, description, status
- `AgentCollectionModel` — id, agent_id, collection_id
- `DocumentModel` — id, project_id, collection_id, title, file_name, content_type, size_bytes, storage_key, parser, status, error, page_count, chunk_count, sha256, indexed_at
- `DocumentChunkModel` — id, project_id, collection_id, document_id, content, chunk_index, token_count, page_number, section_title, metadata, embedding
- `OutboxEventModel`, `InboxEventModel` — schema: knowledge

### runtime (schema: runtime)
- `SessionModel` — id, project_id, agent_id, external_session_id, tenant_id, user_id, status, metadata, last_message_at
- `MessageModel` — id, project_id, agent_id, session_id, role, content, input_tokens, output_tokens, cost_usd, metadata
- `OutboxEventModel`, `InboxEventModel` — schema: runtime

### tools (schema: tools)
- `ToolModel` — id, project_id, agent_id, name, description, type, config, input_schema, output_schema, risk_level, timeout_ms, status
- `SecretModel` — id, project_id, name, type, encrypted_value, metadata
- `OutboxEventModel`, `InboxEventModel` — schema: tools

### metering (schema: metering)
- `UsageEventModel` — id, project_id, agent_id, event_type, quantity, unit, cost_usd, metadata
- `UsageDailyProjectModel` — project_id, day, requests, input_tokens, output_tokens, embedding_tokens, tool_calls, vector_queries, storage_mb, cost_usd
- `UsageDailyAgentModel` — agent_id, day, project_id, requests, input_tokens, output_tokens, tool_calls, vector_queries, cost_usd
- `OutboxEventModel`, `InboxEventModel` — schema: metering

### billing (schema: billing)
- `PlanModel` — id, code, name, price_usd, billing_interval, limits, status
- `CustomerModel` — id, organization_id, provider, provider_customer_id, email, metadata
- `SubscriptionModel` — id, organization_id, customer_id, plan_id, provider, provider_subscription_id, status, current_period_start, current_period_end, trial_ends_at, canceled_at
- `PaymentEventModel` — id, provider, provider_event_id, event_type, payload, status, processed_at
- `OutboxEventModel`, `InboxEventModel` — schema: billing

### observability (schema: observability)
- `TraceModel` — id, project_id, agent_id, session_id, external_session_id, tenant_id, user_id, status, started_at, ended_at, total_latency_ms, total_cost_usd, provider, model, fallback_used, error, metadata
- `TraceEventModel` — id, trace_id, project_id, event_type, latency_ms, cost_usd, payload, payload_ref
- `OutboxEventModel`, `InboxEventModel` — schema: observability

## Fase 4 — Domínio (por módulo)

Para cada módulo, criar em `domain/`:

### `entities.py`
Classes puras do domínio (dataclasses ou Pydantic):
- Ex: `User`, `Organization`, `Project`, `ApiKey`, `Agent`, etc.
- Sem dependência de SQLAlchemy ou FastAPI

### `repositories.py`
Interfaces ABCs dos repositórios:
- Ex: `class UserRepository(ABC)` com `add`, `get_by_id`, `get_by_email`, `list`, etc.
- Ex: `class ProjectRepository(ABC)` com `add`, `get_by_id`, `list_by_organization`, etc.

### `errors.py`
Erros específicos do módulo:
- Ex: `EmailAlreadyExistsError`, `OrganizationNotFoundError`, `ProjectNotFoundError`

### `enums.py`
Enums do módulo:
- Ex: `UserStatus(active, inactive, blocked, deleted)`
- Ex: `ProjectStatus`, `AgentStatus`, `SessionMode`, etc.

---

## Resumo de Arquivos

| Fase | Arquivos |
|------|----------|
| Fase 1 | ~85 `__init__.py` + `main.py` |
| Fase 2 | ~15 arquivos (base, session_manager, config, crypto, objects, errors, repositories, outbox, inbox, etc.) |
| Fase 3 | 9 módulos × ~7-10 models + outbox/inbox = ~70-90 models |
| Fase 4 | 9 módulos × 4 arquivos (entities, repositories, errors, enums) = 36 arquivos |

Total Fases 1-4: ~130-140 arquivos
