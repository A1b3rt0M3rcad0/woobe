# Objetos dos schemas

*Populado na spec 001 via análise estática dos modelos SQLAlchemy.*

## Tabelas de negócio — schema `ai` (target: `agent`)

| Tabela | Modelo | Classe |
|---|---|---|
| `ai.provider_credentials` | `ProviderCredentialModel` | src/modules/agent/infra/database/models.py |
| `ai.agents` | `AgentModel` | src/modules/agent/infra/database/models.py |
| `ai.agent_prompts` | `AgentPromptModel` | src/modules/agent/infra/database/models.py |
| `ai.agent_contracts` | `AgentContractModel` | src/modules/agent/infra/database/models.py |
| `ai.agent_model_configs` | `AgentModelConfigModel` | src/modules/agent/infra/database/models.py |
| `ai.agent_releases` | `AgentReleaseModel` | src/modules/agent/infra/database/models.py |
| `ai.agent_release_tests` | `AgentReleaseTestModel` | src/modules/agent/infra/database/models.py |

## Tabelas de mensageria legadas — schema `ai` (target: `agent`)

| Tabela | Modelo | Nota |
|---|---|---|
| `ai.outbox_events` | `AiOutboxEventModel` | Renomear para evitar conflito |
| `ai.inbox_events` | `AiInboxEventModel` | Renomear para evitar conflito |

## Tabelas de negócio — schema `knowledge` (target: `agent`)

| Tabela | Modelo | Classe |
|---|---|---|
| `knowledge.document_collections` | `DocumentCollectionModel` | src/modules/agent/infra/database/models.py |
| `knowledge.agent_collections` | `AgentCollectionModel` | src/modules/agent/infra/database/models.py |
| `knowledge.documents` | `DocumentModel` | src/modules/agent/infra/database/models.py |
| `knowledge.document_chunks` | `DocumentChunkModel` | src/modules/agent/infra/database/models.py |
| `knowledge.knowledge_versions` | `KnowledgeVersionModel` | src/modules/agent/infra/database/models.py |

## Tabelas de mensageria legadas — schema `knowledge` (target: `agent`)

| Tabela | Modelo | Nota |
|---|---|---|
| `knowledge.outbox_events` | `KnowledgeOutboxEventModel` | Renomear para evitar conflito |
| `knowledge.inbox_events` | `KnowledgeInboxEventModel` | Renomear para evitar conflito |

## Tabelas de negócio — schema `runtime` (target: `agent`)

| Tabela | Modelo | Classe |
|---|---|---|
| `runtime.sessions` | `SessionModel` | src/modules/agent/infra/database/models.py |
| `runtime.messages` | `MessageModel` | src/modules/agent/infra/database/models.py |
| `runtime.ask_jobs` | `AskJobModel` | src/modules/agent/infra/database/models.py |

## Tabelas de mensageria legadas — schema `runtime` (target: `agent`)

| Tabela | Modelo | Nota |
|---|---|---|
| `runtime.outbox_events` | `RuntimeOutboxEventModel` | Renomear para evitar conflito |
| `runtime.inbox_events` | `RuntimeInboxEventModel` | Renomear para evitar conflito |

## Tabelas canônicas — schema `agent` (já corretas)

| Tabela | Modelo | Classe |
|---|---|---|
| `agent.agent_outbox_events` | `AgentOutboxEventModel` | src/modules/agent/infra/database/models.py |
| `agent.agent_inbox_events` | `AgentInboxEventModel` | src/modules/agent/infra/database/models.py |

## Tabelas de outros módulos (não escopo)

Schemas `core`, `identity`, `billing`, `metering`, `observability`, `tools` — inalterados.

## Pendências

- Verificação de objetos não-modelados (views, funções, triggers) requer acesso ao banco PostgreSQL.
- Row counts e checksums requerem acesso ao banco.
