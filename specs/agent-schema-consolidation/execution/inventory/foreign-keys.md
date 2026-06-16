# Inventário de Foreign Keys

*Populado na spec 001 via análise estática. FKs reais do banco pendentes de verificação.*

## Classificação

- **Intra-agent futuro**: FK entre tabelas que pertencerão ao schema `agent` (ai → ai, knowledge → knowledge, runtime → runtime, ou entre legados)
- **Cross-module**: FK entre tabelas de módulos diferentes (ex: agent → core, agent → identity)
- **Legacy messaging**: FK em tabelas `outbox_events`/`inbox_events` legadas

## FKs intra-agent futuras (todas em `src/modules/agent/infra/database/models.py`)

### provider_credentials → ai.provider_credentials (auto-ref)
- `fallback_credential_id` → `ai.provider_credentials.id`
- `provider_credential_id` (em AgentModel) → `ai.provider_credentials.id`
- `provider_credential_id` (em AgentPromptModel) → `ai.provider_credentials.id`
- `provider_credential_id` (em AgentReleaseModel) → `ai.provider_credentials.id`
- `provider_credential_id` (em ProviderCredentialModel) → `ai.provider_credentials.id`

### agents → ai.agents
- `ProviderCredentialModel.agent_id` → `ai.agents.id`
- `AgentPromptModel.agent_id` → `ai.agents.id`
- `AgentContractModel.agent_id` → `ai.agents.id`
- `AgentModelConfigModel.agent_id` → `ai.agents.id`
- `AgentReleaseModel.agent_id` → `ai.agents.id`
- `AgentReleaseTestModel.agent_id` → `ai.agents.id`
- `AgentCollectionModel.agent_id` → `ai.agents.id`
- `KnowledgeVersionModel.agent_id` → `ai.agents.id`
- `SessionModel.agent_id` → `ai.agents.id`
- `MessageModel.agent_id` → `ai.agents.id`
- `AskJobModel.agent_id` → `ai.agents.id`

### Intra-knowledge
- `DocumentModel.collection_id` → `knowledge.document_collections.id`
- `DocumentChunkModel.document_id` → `knowledge.documents.id`
- `DocumentChunkModel.collection_id` → `knowledge.document_collections.id`
- `AgentCollectionModel.collection_id` → `knowledge.document_collections.id`

### Intra-agent versioning (ai → ai)
- `AgentReleaseModel.prompt_version_id` → `ai.agent_prompts.id`
- `AgentReleaseModel.contract_version_id` → `ai.agent_contracts.id`
- `AgentReleaseModel.model_config_version_id` → `ai.agent_model_configs.id`
- `AgentReleaseModel.knowledge_version_id` → `knowledge.knowledge_versions.id`
- `AgentReleaseTestModel.release_id` → `ai.agent_releases.id`
- `AgentReleaseTestModel.contract_version_id` → `ai.agent_contracts.id`

### Intra-runtime
- `MessageModel.session_id` → `runtime.sessions.id`
- `AskJobModel.session_id` → `runtime.sessions.id`

## FKs cross-module (devem ser removidas)

### agent → core
- `ProviderCredentialModel.project_id` → `core.projects.id`
- `AgentModel.project_id` → `core.projects.id`
- `AgentPromptModel.project_id` → `core.projects.id`
- `AgentContractModel.project_id` → `core.projects.id`
- `AgentModelConfigModel.project_id` → `core.projects.id`
- `AgentReleaseModel.project_id` → `core.projects.id`
- `AgentReleaseTestModel.project_id` → `core.projects.id`
- `DocumentCollectionModel.project_id` → `core.projects.id`
- `AgentCollectionModel.project_id` → `core.projects.id`
- `DocumentModel.project_id` → `core.projects.id`
- `DocumentChunkModel.project_id` → `core.projects.id`
- `KnowledgeVersionModel.project_id` → `core.projects.id`
- `SessionModel.project_id` → `core.projects.id`
- `MessageModel.project_id` → `core.projects.id`
- `AskJobModel.project_id` → `core.projects.id`

### agent → identity
- `AgentReleaseModel.created_by` → `identity.users.id`
- `AgentReleaseModel.promoted_by` → `identity.users.id`
- `AgentPromptModel.created_by` → `identity.users.id`

### metering → ai
- `UsageEventModel.agent_id` → `ai.agents.id`
- `UsageDailyAgentModel.agent_id` → `ai.agents.id`

### observability → ai, runtime
- `TraceEventModel.agent_id` → `ai.agents.id`
- `TraceEventModel.session_id` → `runtime.sessions.id`

### tools → ai
- `ToolModel.agent_id` → `ai.agents.id`

## FKs em migrations históricas

A migration `0002_create_all_tables.py` cria todas as FKs listadas acima via `sa.ForeignKeyConstraint` e `sa.ForeignKey`. As migrations `0007`, `0008`, `0011` adicionam FKs adicionais.

## Pendências

- Verificação de FKs reais no banco PostgreSQL (pg_constraint) pendente.
- FKs de outros módulos para schemas legados (ai, knowledge, runtime) precisam ser re-apontadas para `agent` ou removidas.
