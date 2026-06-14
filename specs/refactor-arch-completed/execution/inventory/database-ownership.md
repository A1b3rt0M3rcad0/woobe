# Database Ownership Map

Spec: `005-create-current-database-ownership-map`
Date: 2026-06-13
Agent: opencode/deepseek-v4-pro

## Detection commands executed

```bash
grep "__tablename__|__table_args__|ForeignKey|schema=" src/modules/**/*.py
grep "__tablename__|__table_args__|ForeignKey|op.create_foreign_key|schema=" migrations/**/*.py
```

Evidence gathered from:
- `src/modules/identity/infra/models.py`
- `src/modules/core/infra/models.py`
- `src/modules/ai/infra/models.py`
- `src/modules/knowledge/infra/models.py`
- `src/modules/runtime/infra/models.py`
- `src/modules/tools/infra/models.py`
- `src/modules/metering/infra/models.py`
- `src/modules/billing/infra/models.py`
- `src/modules/observability/infra/models.py`
- `migrations/versions/0001_create_schemas.py`
- `migrations/versions/0002_create_all_tables.py`
- `migrations/versions/0006_add_ask_jobs_table.py`
- `migrations/versions/0007_create_agent_versioning_tables.py`
- `migrations/env.py`

## Schemas

Created in `migrations/versions/0001_create_schemas.py`:

| Schema | Owner Module | Status |
|---|---|---|
| identity | identity | stable |
| core | core | stable |
| ai | ai (→ agent) | legacy, migrating to agent |
| knowledge | knowledge (→ agent) | legacy, migrating to agent |
| runtime | runtime (→ agent) | legacy, migrating to agent |
| tools | tools | stable |
| metering | metering | stable |
| billing | billing | stable |
| observability | observability | stable |

## Table ownership map

### Schema: identity

| Table | Model Class | File | Line |
|---|---|---|---|
| users | UserModel | src/modules/identity/infra/models.py | 22 |
| organizations | OrganizationModel | src/modules/identity/infra/models.py | 31 |
| organization_members | OrganizationMemberModel | src/modules/identity/infra/models.py | 44 |
| organization_invites | OrganizationInviteModel | src/modules/identity/infra/models.py | 62 |
| user_sessions | UserSessionModel | src/modules/identity/infra/models.py | 81 |
| outbox_events | OutboxEventModel | src/modules/identity/infra/models.py | 93 |
| inbox_events | InboxEventModel | src/modules/identity/infra/models.py | 98 |

### Schema: core

| Table | Model Class | File | Line |
|---|---|---|---|
| projects | ProjectModel | src/modules/core/infra/models.py | 22 |
| api_keys | ApiKeyModel | src/modules/core/infra/models.py | 38 |
| outbox_events | OutboxEventModel | src/modules/core/infra/models.py | 54 |
| inbox_events | InboxEventModel | src/modules/core/infra/models.py | 59 |

### Schema: ai (legacy → agent)

| Table | Model Class | File | Line |
|---|---|---|---|
| provider_credentials | ProviderCredentialModel | src/modules/ai/infra/models.py | 24 |
| agents | AgentModel | src/modules/ai/infra/models.py | 40 |
| agent_prompts | AgentPromptModel | src/modules/ai/infra/models.py | 76 |
| agent_contracts | AgentContractModel | src/modules/ai/infra/models.py | 90 |
| agent_model_configs | AgentModelConfigModel | src/modules/ai/infra/models.py | 107 |
| agent_releases | AgentReleaseModel | src/modules/ai/infra/models.py | 127 |
| agent_release_tests | AgentReleaseTestModel | src/modules/ai/infra/models.py | 178 |
| outbox_events | OutboxEventModel | src/modules/ai/infra/models.py | 66 |
| inbox_events | InboxEventModel | src/modules/ai/infra/models.py | 71 |

### Schema: knowledge (legacy → agent)

| Table | Model Class | File | Line |
|---|---|---|---|
| document_collections | DocumentCollectionModel | src/modules/knowledge/infra/models.py | 16 |
| agent_collections | AgentCollectionModel | src/modules/knowledge/infra/models.py | 26 |
| documents | DocumentModel | src/modules/knowledge/infra/models.py | 39 |
| document_chunks | DocumentChunkModel | src/modules/knowledge/infra/models.py | 61 |
| knowledge_versions | KnowledgeVersionModel | src/modules/knowledge/infra/models.py | 79 |
| outbox_events | OutboxEventModel | src/modules/knowledge/infra/models.py | 92 |
| inbox_events | InboxEventModel | src/modules/knowledge/infra/models.py | 97 |

### Schema: runtime (legacy → agent)

| Table | Model Class | File | Line |
|---|---|---|---|
| sessions | SessionModel | src/modules/runtime/infra/models.py | 15 |
| messages | MessageModel | src/modules/runtime/infra/models.py | 33 |
| ask_jobs | AskJobModel | src/modules/runtime/infra/models.py | 48 |
| outbox_events | OutboxEventModel | src/modules/runtime/infra/models.py | 64 |
| inbox_events | InboxEventModel | src/modules/runtime/infra/models.py | 69 |

### Schema: tools

| Table | Model Class | File | Line |
|---|---|---|---|
| tools | ToolModel | src/modules/tools/infra/models.py | 14 |
| secrets | SecretModel | src/modules/tools/infra/models.py | 31 |
| outbox_events | OutboxEventModel | src/modules/tools/infra/models.py | 45 |
| inbox_events | InboxEventModel | src/modules/tools/infra/models.py | 50 |

### Schema: metering

| Table | Model Class | File | Line |
|---|---|---|---|
| usage_events | (inferred UsageEventModel) | src/modules/metering/infra/models.py | 16 |
| usage_daily_project | (inferred UsageDailyProjectModel) | src/modules/metering/infra/models.py | 29 |
| usage_daily_agent | (inferred UsageDailyAgentModel) | src/modules/metering/infra/models.py | 48 |
| outbox_events | OutboxEventModel | src/modules/metering/infra/models.py | 66 |
| inbox_events | InboxEventModel | src/modules/metering/infra/models.py | 71 |

### Schema: billing

| Table | Model Class | File | Line |
|---|---|---|---|
| plans | PlanModel | src/modules/billing/infra/models.py | 15 |
| customers | CustomerModel | src/modules/billing/infra/models.py | 27 |
| subscriptions | SubscriptionModel | src/modules/billing/infra/models.py | 43 |
| payment_events | PaymentEventModel | src/modules/billing/infra/models.py | 61 |
| outbox_events | OutboxEventModel | src/modules/billing/infra/models.py | 76 |
| inbox_events | InboxEventModel | src/modules/billing/infra/models.py | 81 |

### Schema: observability

| Table | Model Class | File | Line |
|---|---|---|---|
| traces | TraceModel | src/modules/observability/infra/models.py | 15 |
| trace_events | TraceEventModel | src/modules/observability/infra/models.py | 39 |
| outbox_events | OutboxEventModel | src/modules/observability/infra/models.py | 52 |
| inbox_events | InboxEventModel | src/modules/observability/infra/models.py | 57 |

## Foreign Key inventory

### Classification legend

- `intra_module`: FK within the same module (allowed in final state)
- `legacy_ai_knowledge_runtime_unification`: FK between ai, knowledge, runtime schemas (will become intra-module after consolidation into agent)
- `cross_module_blocker`: physical FK crossing module boundaries (must be removed in final state, replaced by opaque ID reference or event-driven projection)

### Intra-module FKs (allowed)

| Source Table | Column | Target | File | Line |
|---|---|---|---|---|
| identity.organization_members | user_id | identity.users.id | src/modules/identity/infra/models.py | 50 |
| identity.organization_members | organization_id | identity.organizations.id | src/modules/identity/infra/models.py | 51 |
| identity.organization_invites | organization_id | identity.organizations.id | src/modules/identity/infra/models.py | 68 |
| identity.organization_invites | invited_by_user_id | identity.users.id | src/modules/identity/infra/models.py | 74 |
| identity.user_sessions | user_id | identity.users.id | src/modules/identity/infra/models.py | 84 |
| core.api_keys | project_id | core.projects.id | src/modules/core/infra/models.py | 42 |
| ai.agents | provider_credential_id | ai.provider_credentials.id | src/modules/ai/infra/models.py | 45 |
| ai.agents | fallback_credential_id | ai.provider_credentials.id | src/modules/ai/infra/models.py | 48 |
| ai.agent_prompts | agent_id | ai.agents.id | src/modules/ai/infra/models.py | 81 |
| ai.agent_contracts | agent_id | ai.agents.id | src/modules/ai/infra/models.py | 95 |
| ai.agent_model_configs | agent_id | ai.agents.id | src/modules/ai/infra/models.py | 112 |
| ai.agent_model_configs | provider_credential_id | ai.provider_credentials.id | src/modules/ai/infra/models.py | 115 |
| ai.agent_releases | agent_id | ai.agents.id | src/modules/ai/infra/models.py | 132 |
| ai.agent_releases | prompt_version_id | ai.agent_prompts.id | src/modules/ai/infra/models.py | 135 |
| ai.agent_releases | contract_version_id | ai.agent_contracts.id | src/modules/ai/infra/models.py | 138 |
| ai.agent_releases | model_config_version_id | ai.agent_model_configs.id | src/modules/ai/infra/models.py | 144 |
| ai.agent_releases | provider_credential_id | ai.provider_credentials.id | src/modules/ai/infra/models.py | 155 |
| ai.agent_releases | fallback_credential_id | ai.provider_credentials.id | src/modules/ai/infra/models.py | 160 |
| ai.agent_release_tests | agent_id | ai.agents.id | src/modules/ai/infra/models.py | 183 |
| ai.agent_release_tests | release_id | ai.agent_releases.id | src/modules/ai/infra/models.py | 184 |
| ai.agent_release_tests | contract_version_id | ai.agent_contracts.id | src/modules/ai/infra/models.py | 187 |
| knowledge.agent_collections | collection_id | knowledge.document_collections.id | src/modules/knowledge/infra/models.py | 34 |
| knowledge.documents | collection_id | knowledge.document_collections.id | src/modules/knowledge/infra/models.py | 44 |
| knowledge.document_chunks | collection_id | knowledge.document_collections.id | src/modules/knowledge/infra/models.py | 66 |
| knowledge.document_chunks | document_id | knowledge.documents.id | src/modules/knowledge/infra/models.py | 69 |
| runtime.messages | session_id | runtime.sessions.id | src/modules/runtime/infra/models.py | 39 |
| runtime.ask_jobs | session_id | runtime.sessions.id | src/modules/runtime/infra/models.py | 54 |
| billing.subscriptions | customer_id | billing.customers.id | src/modules/billing/infra/models.py | 50 |
| billing.subscriptions | plan_id | billing.plans.id | src/modules/billing/infra/models.py | 51 |
| observability.trace_events | trace_id | observability.traces.id | src/modules/observability/infra/models.py | 43 |

### Legacy ai/knowledge/runtime unification FKs (will become intra-module in agent)

| Source Table | Column | Target | File | Line | Migration Impact |
|---|---|---|---|---|---|
| ai.agent_releases | knowledge_version_id | knowledge.knowledge_versions.id | src/modules/ai/infra/models.py | 141 | FK will be internal to `agent` schema after consolidation |
| knowledge.agent_collections | agent_id | ai.agents.id | src/modules/knowledge/infra/models.py | 33 | FK will be internal to `agent` schema after consolidation |
| knowledge.knowledge_versions | agent_id | ai.agents.id | src/modules/knowledge/infra/models.py | 84 | FK will be internal to `agent` schema after consolidation |
| runtime.sessions | agent_id | ai.agents.id | src/modules/runtime/infra/models.py | 23 | FK will be internal to `agent` schema after consolidation |
| runtime.messages | agent_id | ai.agents.id | src/modules/runtime/infra/models.py | 38 | FK will be internal to `agent` schema after consolidation |
| runtime.ask_jobs | agent_id | ai.agents.id | src/modules/runtime/infra/models.py | 53 | FK will be internal to `agent` schema after consolidation |

### Cross-module blocker FKs (must be removed in final state)

Physical FKs that cross module boundaries. These must be replaced by opaque ID references (column without constraint) or event-driven projections.

| Source Table | Column | Target | Owner Module | Target Module | File | Line | Spec Responsible | Risk |
|---|---|---|---|---|---|---|---|---|
| core.projects | organization_id | identity.organizations.id | core | identity | src/modules/core/infra/models.py | 30 | 134 | core depends on identity; replace with opaque ref |
| core.api_keys | created_by_user_id | identity.users.id | core | identity | src/modules/core/infra/models.py | 51 | 134 | core depends on identity; replace with opaque ref |
| ai.provider_credentials | project_id | core.projects.id | ai (→agent) | core | src/modules/ai/infra/models.py | 31 | 134 | agent depends on core; replace with opaque ref |
| ai.agents | project_id | core.projects.id | ai (→agent) | core | src/modules/ai/infra/models.py | 44 | 134 | agent depends on core; replace with opaque ref |
| ai.agent_prompts | project_id | core.projects.id | ai (→agent) | core | src/modules/ai/infra/models.py | 80 | 134 | agent depends on core; replace with opaque ref |
| ai.agent_prompts | created_by | identity.users.id | ai (→agent) | identity | src/modules/ai/infra/models.py | 87 | 134 | agent depends on identity; replace with opaque ref |
| ai.agent_contracts | project_id | core.projects.id | ai (→agent) | core | src/modules/ai/infra/models.py | 94 | 134 | agent depends on core; replace with opaque ref |
| ai.agent_model_configs | project_id | core.projects.id | ai (→agent) | core | src/modules/ai/infra/models.py | 111 | 134 | agent depends on core; replace with opaque ref |
| ai.agent_releases | project_id | core.projects.id | ai (→agent) | core | src/modules/ai/infra/models.py | 131 | 134 | agent depends on core; replace with opaque ref |
| ai.agent_releases | created_by | identity.users.id | ai (→agent) | identity | src/modules/ai/infra/models.py | 173 | 134 | agent depends on identity; replace with opaque ref |
| ai.agent_releases | promoted_by | identity.users.id | ai (→agent) | identity | src/modules/ai/infra/models.py | 174 | 134 | agent depends on identity; replace with opaque ref |
| ai.agent_release_tests | project_id | core.projects.id | ai (→agent) | core | src/modules/ai/infra/models.py | 182 | 134 | agent depends on core; replace with opaque ref |
| knowledge.document_collections | project_id | core.projects.id | knowledge (→agent) | core | src/modules/knowledge/infra/models.py | 20 | 134 | agent depends on core; replace with opaque ref |
| knowledge.documents | project_id | core.projects.id | knowledge (→agent) | core | src/modules/knowledge/infra/models.py | 43 | 134 | agent depends on core; replace with opaque ref |
| knowledge.document_chunks | project_id | core.projects.id | knowledge (→agent) | core | src/modules/knowledge/infra/models.py | 65 | 134 | agent depends on core; replace with opaque ref |
| knowledge.knowledge_versions | project_id | core.projects.id | knowledge (→agent) | core | src/modules/knowledge/infra/models.py | 83 | 134 | agent depends on core; replace with opaque ref |
| runtime.sessions | project_id | core.projects.id | runtime (→agent) | core | src/modules/runtime/infra/models.py | 22 | 134 | agent depends on core; replace with opaque ref |
| runtime.messages | project_id | core.projects.id | runtime (→agent) | core | src/modules/runtime/infra/models.py | 37 | 134 | agent depends on core; replace with opaque ref |
| runtime.ask_jobs | project_id | core.projects.id | runtime (→agent) | core | src/modules/runtime/infra/models.py | 52 | 134 | agent depends on core; replace with opaque ref |
| tools.tools | project_id | core.projects.id | tools | core | src/modules/tools/infra/models.py | 18 | 134 | tools depends on core; replace with opaque ref |
| tools.tools | agent_id | ai.agents.id | tools | ai (→agent) | src/modules/tools/infra/models.py | 19 | 134 | tools depends on agent; replace with opaque ref |
| tools.secrets | project_id | core.projects.id | tools | core | src/modules/tools/infra/models.py | 38 | 134 | tools depends on core; replace with opaque ref |
| metering.usage_events | project_id | core.projects.id | metering | core | src/modules/metering/infra/models.py | 19 | 134 | metering depends on core; replace with opaque ref |
| metering.usage_events | agent_id | ai.agents.id | metering | ai (→agent) | src/modules/metering/infra/models.py | 20 | 134 | metering depends on agent; replace with opaque ref |
| metering.usage_daily_project | project_id | core.projects.id | metering | core | src/modules/metering/infra/models.py | 33 | 134 | metering depends on core; replace with opaque ref |
| metering.usage_daily_agent | agent_id | ai.agents.id | metering | ai (→agent) | src/modules/metering/infra/models.py | 52 | 134 | metering depends on agent; replace with opaque ref |
| metering.usage_daily_agent | project_id | core.projects.id | metering | core | src/modules/metering/infra/models.py | 55 | 134 | metering depends on core; replace with opaque ref |
| observability.traces | project_id | core.projects.id | observability | core | src/modules/observability/infra/models.py | 19 | 134 | observability depends on core; replace with opaque ref |
| observability.traces | agent_id | ai.agents.id | observability | ai (→agent) | src/modules/observability/infra/models.py | 20 | 134 | observability depends on agent; replace with opaque ref |
| observability.traces | session_id | runtime.sessions.id | observability | runtime (→agent) | src/modules/observability/infra/models.py | 21 | 134 | observability depends on agent; replace with opaque ref |
| observability.trace_events | project_id | core.projects.id | observability | core | src/modules/observability/infra/models.py | 44 | 134 | observability depends on core; replace with opaque ref |
| billing.customers | organization_id | identity.organizations.id | billing | identity | src/modules/billing/infra/models.py | 34 | 134 | billing depends on identity; replace with opaque ref |
| billing.subscriptions | organization_id | identity.organizations.id | billing | identity | src/modules/billing/infra/models.py | 47 | 134 | billing depends on identity; replace with opaque ref |

## Cross-module foreign keys to remove before final state

Total cross-module physical FKs: **33**

Summary by dependency direction:

| Source Module | Target Module | Count | Impact |
|---|---|---|---|
| ai (→agent) | core | 8 | project_id references |
| ai (→agent) | identity | 3 | created_by, promoted_by references |
| knowledge (→agent) | core | 4 | project_id references |
| runtime (→agent) | core | 3 | project_id references |
| tools | core | 2 | project_id references |
| tools | ai (→agent) | 1 | agent_id reference |
| metering | core | 3 | project_id references |
| metering | ai (→agent) | 2 | agent_id references |
| observability | core | 2 | project_id references |
| observability | ai (→agent) | 1 | agent_id reference |
| observability | runtime (→agent) | 1 | session_id reference |
| billing | identity | 2 | organization_id references |
| core | identity | 2 | organization_id, user_id references |

All 33 cross-module physical FKs are incompatible with the final architectural state. They must be converted to opaque ID columns without constraint during spec 134 (expand-migrate-contract).

## Outbox/Inbox tables per module

Every module has its own `outbox_events` and `inbox_events` tables in its own schema. This is consistent with the target architecture where Outbox/Inbox is per-module.

| Module | Outbox Table | Inbox Table |
|---|---|---|
| identity | identity.outbox_events | identity.inbox_events |
| core | core.outbox_events | core.inbox_events |
| ai (→agent) | ai.outbox_events | ai.inbox_events |
| knowledge (→agent) | knowledge.outbox_events | knowledge.inbox_events |
| runtime (→agent) | runtime.outbox_events | runtime.inbox_events |
| tools | tools.outbox_events | tools.inbox_events |
| metering | metering.outbox_events | metering.inbox_events |
| billing | billing.outbox_events | billing.inbox_events |
| observability | observability.outbox_events | observability.inbox_events |

After migration, ai/knowledge/runtime outbox_events and inbox_events should be consolidated into a single `agent.outbox_events` and `agent.inbox_events` (spec 070-076).

## Alembic/migrations metadata

`migrations/env.py` (line 15-23) imports all module models explicitly:
- `modules.identity.infra.models`
- `modules.core.infra.models`
- `modules.ai.infra.models`
- `modules.knowledge.infra.models`
- `modules.runtime.infra.models`
- `modules.tools.infra.models`
- `modules.metering.infra.models`
- `modules.billing.infra.models`
- `modules.observability.infra.models`

After migration, `modules.ai`, `modules.knowledge`, and `modules.runtime` imports must be replaced by `modules.agent.infra.models` (spec 134).

## Risks identified

| Risk | Severity | Evidence | Affected Specs |
|---|---|---|---|
| 33 cross-module physical FKs violate final architecture | high | All modules use ForeignKey() to reference core.projects.id and identity tables | 134 |
| ai.agent_releases references knowledge.knowledge_versions.id | medium | src/modules/ai/infra/models.py:141 | 020-025, 074 |
| observability.traces references runtime.sessions.id | medium | src/modules/observability/infra/models.py:21 | 134 |
| tools.tools references ai.agents.id | medium | src/modules/tools/infra/models.py:19 | 134 |
| metering.usage_events and usage_daily_agent reference ai.agents.id | medium | src/modules/metering/infra/models.py:20,52 | 134 |
| Three separate Outbox/Inbox tables in ai, knowledge, runtime must merge | medium | Three separate schema Outbox/Inbox pairs | 070-076 |
| Alembic env.py hardcodes legacy module imports | low | migrations/env.py:17-19 | 134 |

## Inconsistencies

- `knowledge.knowledge_versions.agent_id → ai.agents.id`: knowledge references ai directly with physical FK. This is an `ai↔knowledge` coupling that will become intra-module in `agent`.
- `knowledge.agent_collections.agent_id → ai.agents.id`: same pattern.
- `runtime.sessions.agent_id → ai.agents.id`, `runtime.messages.agent_id → ai.agents.id`, `runtime.ask_jobs.agent_id → ai.agents.id`: runtime references ai directly. These become intra-module in `agent`.
- `observability.traces.session_id → runtime.sessions.id`: observability crosses into runtime (future agent). This remains cross-module even after agent consolidation.
