# Mapa de tabelas source → agent

*Populado na spec 002.*

## Tabelas de negócio — source `ai.*` → target `agent.*`

| Source | Target | SET SCHEMA direto? | Notas |
|---|---|---|---|
| `ai.provider_credentials` | `agent.provider_credentials` | Sim | Nome único |
| `ai.agents` | `agent.agents` | Sim | Nome único |
| `ai.agent_prompts` | `agent.agent_prompts` | Sim | Nome único |
| `ai.agent_contracts` | `agent.agent_contracts` | Sim | Nome único |
| `ai.agent_model_configs` | `agent.agent_model_configs` | Sim | Nome único |
| `ai.agent_releases` | `agent.agent_releases` | Sim | Nome único |
| `ai.agent_release_tests` | `agent.agent_release_tests` | Sim | Nome único |

## Tabelas de negócio — source `knowledge.*` → target `agent.*`

| Source | Target | SET SCHEMA direto? | Notas |
|---|---|---|---|
| `knowledge.document_collections` | `agent.document_collections` | Sim | Nome único |
| `knowledge.agent_collections` | `agent.agent_collections` | Sim | Nome único |
| `knowledge.documents` | `agent.documents` | Sim | Nome único |
| `knowledge.document_chunks` | `agent.document_chunks` | Sim | Nome único |
| `knowledge.knowledge_versions` | `agent.knowledge_versions` | Sim | Nome único |

## Tabelas de negócio — source `runtime.*` → target `agent.*`

| Source | Target | SET SCHEMA direto? | Notas |
|---|---|---|---|
| `runtime.sessions` | `agent.sessions` | Sim | Nome único |
| `runtime.messages` | `agent.messages` | Sim | Nome único |
| `runtime.ask_jobs` | `agent.ask_jobs` | Sim | Nome único |

## Tabelas de mensageria legadas — requerem rename prévio

| Source | Target intermediário | Target final | Notas |
|---|---|---|---|
| `ai.outbox_events` | `ai.legacy_outbox_events` (rename) | `agent.legacy_outbox_events` | Conflito de nome com `knowledge.outbox_events` e `runtime.outbox_events` |
| `ai.inbox_events` | `ai.legacy_inbox_events` (rename) | `agent.legacy_inbox_events` | Conflito de nome com `knowledge.inbox_events` e `runtime.inbox_events` |
| `knowledge.outbox_events` | `knowledge.legacy_outbox_events` (rename) | `agent.legacy_outbox_events` | Conflito de nome |
| `knowledge.inbox_events` | `knowledge.legacy_inbox_events` (rename) | `agent.legacy_inbox_events` | Conflito de nome |
| `runtime.outbox_events` | `runtime.legacy_outbox_events` (rename) | `agent.legacy_outbox_events` | Conflito de nome |
| `runtime.inbox_events` | `runtime.legacy_inbox_events` (rename) | `agent.legacy_inbox_events` | Conflito de nome |

## Tabelas canônicas de mensageria (já no schema `agent`)

| Tabela | Modelo | Ação |
|---|---|---|
| `agent.agent_outbox_events` | `AgentOutboxEventModel` | Permanecer inalterada |
| `agent.agent_inbox_events` | `AgentInboxEventModel` | Permanecer inalterada |

## Política de Foreign Keys

### FKs intra-agent (recriar como `agent.* → agent.*`)

Após o SET SCHEMA, todas as FKs que referenciam `ai.*`, `knowledge.*` ou `runtime.*` passarão a referenciar `agent.*` automaticamente (porque a tabela referenciada mudou de schema). No entanto, FKs explícitas com `schema="..."` nos modelos SQLAlchemy precisam ser atualizadas.

### FKs cross-module (remover constraint, manter coluna, criar índice)

| Tabela | Coluna | Referência atual | Ação |
|---|---|---|---|
| `agent.provider_credentials` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.agents` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_prompts` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_prompts` | `created_by` | `identity.users.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_contracts` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_model_configs` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_releases` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_releases` | `created_by` | `identity.users.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_releases` | `promoted_by` | `identity.users.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_release_tests` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.document_collections` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.agent_collections` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.documents` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.document_chunks` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.knowledge_versions` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.sessions` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.messages` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |
| `agent.ask_jobs` | `project_id` | `core.projects.id` | Remover FK, manter UUID, criar índice |

### FKs de outros módulos para agent (re-apontar para `agent.*`)

| Módulo | Tabela | Coluna | Ref. atual | Ação |
|---|---|---|---|---|
| metering | `usage_events` | `agent_id` | `ai.agents.id` | Re-apontar para `agent.agents.id` |
| metering | `usage_daily_agent` | `agent_id` | `ai.agents.id` | Re-apontar para `agent.agents.id` |
| observability | `trace_events` | `agent_id` | `ai.agents.id` | Re-apontar para `agent.agents.id` |
| observability | `trace_events` | `session_id` | `runtime.sessions.id` | Re-apontar para `agent.sessions.id` |
| tools | `tools` | `agent_id` | `ai.agents.id` | Re-apontar para `agent.agents.id` |

## Colisões de nomes identificadas

### Índices
- Não foram identificadas colisões de nomes de índices entre schemas. Cada schema tem seu namespace de índices.

### Constraints
- As FKs que referenciam tabelas em schemas legados precisarão ser recriadas após o SET SCHEMA.
- `UniqueConstraint` em `sessions` (`uq_sessions_project_agent_external`) permanece válida.

### Sequences
- Nenhuma sequence identificada nos modelos. Verificação pendente no banco real.

### Views
- Nenhuma view nos modelos. Verificação pendente no banco real.
