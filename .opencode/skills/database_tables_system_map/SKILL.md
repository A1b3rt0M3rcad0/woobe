---
name: database-tables-system-map
description: Defines the complete database table map for the system, including schemas, table names, columns, ownership, relationships, and naming rules.
---

# Database Tables System Map

## Objective

This skill defines the database structure of the system.

It explains:

```txt
which schemas exist
which tables exist in each schema
which columns each table has
what each table represents
how tables relate to each other
how names should be standardized
```

This skill is focused on the database model.

It is not focused on business logic implementation.

It is not focused on routes.

It is not focused on workers.

It is not focused on UI.

## Main database rule

The system uses PostgreSQL schemas to separate modules.

Each module owns one schema.

Each schema contains the tables of that module.

Example:

```txt
identity.users
core.projects
ai.agents
knowledge.documents
runtime.sessions
tools.tools
metering.usage_events
billing.subscriptions
observability.traces
events.outbox_events
```

The schema name identifies the module.

The table name identifies the entity.

## Schemas

The system has these schemas:

```txt
identity
core
ai
knowledge
runtime
tools
metering
billing
observability
events
```

## Table naming rules

Use plural table names.

Correct:

```txt
users
organizations
projects
api_keys
agents
documents
document_chunks
sessions
messages
tools
usage_events
subscriptions
outbox_events
inbox_events
```

Do not repeat the schema name in the table name.

Correct:

```txt
core.projects
```

Wrong:

```txt
core.core_projects
```

## Column naming rules

Use snake_case.

Correct:

```txt
project_id
organization_id
created_at
updated_at
last_used_at
provider_subscription_id
```

Wrong:

```txt
projectId
organizationId
createdAt
providerSubscriptionId
```

## Common column rules

Most main tables should have:

```txt
id
created_at
updated_at
```

Event and log-like tables may have only:

```txt
id
created_at
```

Every main table should use:

```txt
UUID id
```

Prefer UUIDv7 for IDs.

## Standard column types

Use these conceptual types:

```txt
UUID
string
text
int
bigint
decimal
boolean
datetime
date
JSON
vector
bytes
inet
```

When implementing with PostgreSQL/SQLAlchemy:

```txt
string → String/Text depending on size
JSON → JSONB
datetime → TIMESTAMPTZ / DateTime(timezone=True)
bytes → LargeBinary
vector → pgvector
```

---

# Schema: identity

## Purpose

The `identity` schema owns users, organizations, organization membership, invites, and dashboard sessions.

It answers:

```txt
who is the user?
which organization does the user belong to?
what role does the user have?
is the user authenticated?
```

## Table: identity.users

Represents a human user of the dashboard.

Columns:

```txt
PK UUID id
UQ string email
bytes password
string status
datetime created_at
datetime updated_at
```

Optional future columns:

```txt
string name
string avatar_url
datetime email_verified_at
datetime last_login_at
JSON metadata
```

Notes:

```txt
email must be unique
password should store a hash, not plain text
status controls if the user can access the system
```

Recommended statuses:

```txt
active
inactive
blocked
deleted
```

## Table: identity.organizations

Represents a company, workspace, or customer account.

Columns:

```txt
PK UUID id
string name
UQ string slug
string status
datetime created_at
datetime updated_at
```

Optional future columns:

```txt
JSON metadata
```

Recommended statuses:

```txt
active
suspended
deleted
```

## Table: identity.organization_members

Connects users to organizations.

Columns:

```txt
PK UUID id
FK UUID user_id
FK UUID organization_id
string role
string status
datetime joined_at
datetime created_at
datetime updated_at
```

Recommended unique constraint:

```txt
UNIQUE(organization_id, user_id)
```

Recommended roles:

```txt
owner
admin
developer
viewer
```

Recommended statuses:

```txt
active
inactive
removed
```

## Table: identity.organization_invites

Represents invitations to join an organization.

Columns:

```txt
PK UUID id
FK UUID organization_id
string email
string role
string token_hash
UUID invited_by_user_id
string status
datetime expires_at
datetime accepted_at
datetime created_at
```

Recommended unique constraint:

```txt
UNIQUE(organization_id, email)
```

Recommended statuses:

```txt
pending
accepted
expired
revoked
```

Notes:

```txt
token_hash stores the hashed invite token
the raw token must not be stored
```

## Table: identity.user_sessions

Represents dashboard authentication sessions.

Columns:

```txt
PK UUID id
FK UUID user_id
bytes refresh_token_hash
string user_agent
inet ip_address
datetime revoked_at
datetime expires_at
datetime last_used_at
datetime created_at
datetime updated_at
```

Notes:

```txt
this is not the AI conversation session
this is only for dashboard/user authentication
```

---

# Schema: core

## Purpose

The `core` schema owns projects and API keys.

It answers:

```txt
which project is being accessed?
which API key is being used?
is the project active?
```

## Table: core.projects

Represents a project inside an organization.

Columns:

```txt
PK UUID id
FK UUID organization_id
string name
string slug
string status
JSON metadata
datetime created_at
datetime updated_at
```

Recommended unique constraint:

```txt
UNIQUE(organization_id, slug)
```

Recommended statuses:

```txt
active
inactive
suspended
deleted
```

Notes:

```txt
project is the main operational boundary
most other modules reference project_id
```

## Table: core.api_keys

Represents API keys used to access the runtime API.

Columns:

```txt
PK UUID id
FK UUID project_id
string name
string key_prefix
UQ bytes key_hash
JSON scopes
string status
datetime last_used_at
datetime expires_at
datetime revoked_at
FK UUID created_by_user_id
datetime created_at
```

Recommended statuses:

```txt
active
revoked
expired
```

Recommended scopes:

```txt
ask:write
agents:read
agents:write
documents:read
documents:write
tools:read
tools:write
usage:read
admin
```

Notes:

```txt
never store the raw API key
store only key_prefix and key_hash
the raw key is shown only once during creation
```

---

# Schema: ai

## Purpose

The `ai` schema owns model credentials and agent configuration.

It answers:

```txt
which agent should run?
which provider/model should be used?
which credential should be used?
what is the prompt?
```

## Table: ai.provider_credentials

Represents customer-provided AI provider credentials.

Columns:

```txt
PK UUID id
FK UUID project_id
string provider
string name
string encrypted_secret
string status
datetime last_validated_at
datetime created_at
datetime updated_at
```

Recommended unique constraint:

```txt
UNIQUE(project_id, provider, name)
```

Recommended providers:

```txt
openai
anthropic
google
groq
mistral
azure_openai
custom
```

Recommended statuses:

```txt
active
invalid
disabled
deleted
```

Notes:

```txt
encrypted_secret must store encrypted credential data
raw secrets must not be stored
```

## Table: ai.agents

Represents an AI agent configuration.

Columns:

```txt
PK UUID id
FK UUID project_id
FK UUID provider_credential_id
FK UUID fallback_credential_id
string name
string description
string type
text system_prompt
string provider
string model
string fallback_provider
string fallback_model
decimal temperature
int max_output_tokens
string session_mode
string status
JSON settings
datetime created_at
datetime updated_at
```

Recommended statuses:

```txt
active
inactive
draft
deleted
```

Recommended session modes:

```txt
managed
external
stateless
```

Notes:

```txt
managed = platform stores session/messages
external = customer controls session state outside the platform
stateless = no conversation persistence
```

---

# Schema: knowledge

## Purpose

The `knowledge` schema owns documents, collections, chunks, and embeddings.

It answers:

```txt
what knowledge can the agent use?
which documents are connected?
which chunks are retrieved for RAG?
```

## Table: knowledge.document_collections

Represents a collection of documents.

Columns:

```txt
PK UUID id
FK UUID project_id
string name
string description
string status
datetime created_at
datetime updated_at
```

Recommended statuses:

```txt
active
inactive
deleted
```

Notes:

```txt
collections allow multiple agents to share the same knowledge base
```

## Table: knowledge.agent_collections

Connects agents to document collections.

Columns:

```txt
PK UUID id
FK UUID agent_id
FK UUID collection_id
datetime created_at
```

Recommended unique constraint:

```txt
UNIQUE(agent_id, collection_id)
```

Notes:

```txt
this table creates the many-to-many relation between agents and collections
```

## Table: knowledge.documents

Represents uploaded or connected document metadata.

Columns:

```txt
PK UUID id
FK UUID project_id
FK UUID collection_id
string title
string file_name
string content_type
bigint size_bytes
string storage_key
string parser
string status
string error
int page_count
int chunk_count
string sha256
datetime created_at
datetime updated_at
datetime indexed_at
```

Recommended statuses:

```txt
uploaded
queued
parsing
parsed
chunking
embedding
indexed
failed
deleted
```

Notes:

```txt
the actual file is not stored in the database
storage_key points to object storage
sha256 helps detect duplicates
```

## Table: knowledge.document_chunks

Represents chunks extracted from documents and used for RAG.

Columns:

```txt
PK UUID id
FK UUID project_id
FK UUID collection_id
FK UUID document_id
text content
int chunk_index
int token_count
int page_number
string section_title
JSON metadata
vector embedding
datetime created_at
```

Recommended indexes:

```txt
project_id
collection_id
document_id
embedding vector index
```

Notes:

```txt
embedding uses pgvector initially
search must always filter by project_id and collection_id or agent context
```

---

# Schema: runtime

## Purpose

The `runtime` schema owns conversations and messages.

It answers:

```txt
what is the current conversation?
which messages belong to the session?
what should be persisted after /ask?
```

## Table: runtime.sessions

Represents an AI conversation session.

Columns:

```txt
PK UUID id
FK UUID project_id
FK UUID agent_id
string external_session_id
string tenant_id
string user_id
string status
JSON metadata
datetime created_at
datetime updated_at
datetime last_message_at
```

Recommended unique constraint:

```txt
UNIQUE(project_id, agent_id, external_session_id)
```

Recommended statuses:

```txt
active
closed
expired
deleted
```

Notes:

```txt
external_session_id is the customer's session identifier
tenant_id can represent the customer's tenant/customer/account
user_id can represent the end user inside the customer's app
```

## Table: runtime.messages

Represents user and assistant messages.

Columns:

```txt
PK UUID id
FK UUID project_id
FK UUID agent_id
FK UUID session_id
string role
text content
int input_tokens
int output_tokens
decimal cost_usd
JSON metadata
datetime created_at
```

Recommended roles:

```txt
system
user
assistant
tool
```

Notes:

```txt
messages can be retained depending on plan and session_mode
```

---

# Schema: tools

## Purpose

The `tools` schema owns external tools and secrets.

It answers:

```txt
what can the agent execute?
how does the agent call external systems?
which secret is required?
```

## Table: tools.tools

Represents a tool available to one agent or project.

Columns:

```txt
PK UUID id
FK UUID project_id
FK UUID agent_id
string name
string description
string type
JSON config
JSON input_schema
JSON output_schema
string risk_level
int timeout_ms
string status
datetime created_at
datetime updated_at
```

Recommended tool types:

```txt
http_mcp
webhook
database_readonly
custom
```

Recommended risk levels:

```txt
read_only
write
destructive
restricted
```

Recommended statuses:

```txt
active
inactive
deleted
```

Notes:

```txt
config stores endpoint and execution config
input_schema validates tool input
output_schema describes expected output
```

## Table: tools.secrets

Represents encrypted secrets used by tools or connectors.

Columns:

```txt
PK UUID id
FK UUID project_id
string name
string type
string encrypted_value
JSON metadata
datetime created_at
datetime updated_at
```

Recommended unique constraint:

```txt
UNIQUE(project_id, name)
```

Recommended secret types:

```txt
bearer_token
api_key
basic_auth
database_url
custom
```

Notes:

```txt
encrypted_value must never store plain text
```

---

# Schema: metering

## Purpose

The `metering` schema owns usage and cost tracking.

It answers:

```txt
how much was used?
which project consumed resources?
which agent consumed resources?
what is the estimated cost?
```

## Table: metering.usage_events

Represents raw usage events.

Columns:

```txt
PK UUID id
FK UUID project_id
FK UUID agent_id
string event_type
decimal quantity
string unit
decimal cost_usd
JSON metadata
datetime created_at
```

Recommended event types:

```txt
request
input_tokens
output_tokens
embedding_tokens
tool_call
vector_query
document_storage_mb
trace_storage_mb
```

Recommended units:

```txt
count
tokens
mb
usd
milliseconds
```

Notes:

```txt
this table records usage before aggregation
high-volume installations may later move raw events to analytical storage
```

## Table: metering.usage_daily_project

Represents daily aggregate usage by project.

Columns:

```txt
PK UUID project_id
PK date day
int requests
bigint input_tokens
bigint output_tokens
bigint embedding_tokens
int tool_calls
int vector_queries
decimal storage_mb
decimal cost_usd
datetime updated_at
```

Notes:

```txt
used for dashboards, limits, and billing calculations
```

## Table: metering.usage_daily_agent

Represents daily aggregate usage by agent.

Columns:

```txt
PK UUID agent_id
PK date day
FK UUID project_id
int requests
bigint input_tokens
bigint output_tokens
int tool_calls
int vector_queries
decimal cost_usd
datetime updated_at
```

Notes:

```txt
used to understand agent-level cost and usage
```

---

# Schema: billing

## Purpose

The `billing` schema owns plans, customers, subscriptions, and payment events.

It answers:

```txt
what plan does this organization have?
is the subscription active?
which commercial limits apply?
```

## Table: billing.plans

Represents a commercial plan.

Columns:

```txt
PK UUID id
UQ string code
string name
decimal price_usd
string billing_interval
JSON limits
string status
datetime created_at
datetime updated_at
```

Recommended billing intervals:

```txt
monthly
yearly
usage_based
custom
```

Recommended statuses:

```txt
active
inactive
archived
```

Example limits JSON:

```txt
projects
agents_per_project
messages_per_month
documents_storage_mb
trace_retention_days
tool_calls_per_month
```

## Table: billing.customers

Represents a customer record in a payment provider.

Columns:

```txt
PK UUID id
FK UUID organization_id
string provider
string provider_customer_id
string email
JSON metadata
datetime created_at
datetime updated_at
```

Recommended unique constraint:

```txt
UNIQUE(provider, provider_customer_id)
```

Recommended providers:

```txt
stripe
paddle
manual
```

## Table: billing.subscriptions

Represents an organization's subscription.

Columns:

```txt
PK UUID id
FK UUID organization_id
FK UUID customer_id
FK UUID plan_id
string provider
string provider_subscription_id
string status
datetime current_period_start
datetime current_period_end
datetime trial_ends_at
datetime canceled_at
datetime created_at
datetime updated_at
```

Recommended statuses:

```txt
trialing
active
past_due
canceled
paused
expired
manual
```

## Table: billing.payment_events

Represents incoming payment provider events.

Columns:

```txt
PK UUID id
string provider
string provider_event_id
string event_type
JSON payload
string status
datetime processed_at
datetime created_at
```

Recommended unique constraint:

```txt
UNIQUE(provider, provider_event_id)
```

Recommended statuses:

```txt
pending
processed
failed
ignored
```

---

# Schema: observability

## Purpose

The `observability` schema owns traces and trace events.

It answers:

```txt
what happened during execution?
where did it fail?
which model was used?
which tools were called?
```

## Table: observability.traces

Represents the summary of one runtime execution.

Columns:

```txt
PK UUID id
FK UUID project_id
FK UUID agent_id
FK UUID session_id
string external_session_id
string tenant_id
string user_id
string status
datetime started_at
datetime ended_at
int total_latency_ms
decimal total_cost_usd
string provider
string model
boolean fallback_used
string error
JSON metadata
```

Recommended statuses:

```txt
started
completed
failed
timeout
canceled
```

Notes:

```txt
this table should contain summary information
large payloads should not be stored here
```

## Table: observability.trace_events

Represents detailed events inside a trace.

Columns:

```txt
PK UUID id
FK UUID trace_id
FK UUID project_id
string event_type
int latency_ms
decimal cost_usd
JSON payload
string payload_ref
datetime created_at
```

Recommended event types:

```txt
ask.started
session.loaded
rag.started
rag.completed
llm.started
llm.completed
tool.called
tool.completed
fallback.used
response.completed
usage.recorded
```

Notes:

```txt
payload_ref points to object storage when payload is too large
high-scale installations may later move this table to analytical storage
```

---

# Schema: events

## Purpose

The `events` schema owns internal event propagation.

It answers:

```txt
which event was produced?
was it published?
which event was received?
was it processed?
```

## Table: events.outbox_events

Represents events produced by modules.

Columns:

```txt
PK UUID id
string aggregate_type
UUID aggregate_id
string event_type
int event_version
JSON payload
string status
int attempts
datetime available_at
datetime published_at
string error
UUID correlation_id
UUID causation_id
datetime created_at
```

Recommended statuses:

```txt
pending
publishing
published
failed
dead
```

Notes:

```txt
outbox status means publication status
published means the event was sent out
published does not mean consumed
```

## Table: events.inbox_events

Represents events received for dispatching.

Columns:

```txt
PK UUID id
UNIQUE UUID outbox_origin_id
string aggregate_type
string event_type
int event_version
JSON payload
string status
int attempts
datetime available_at
datetime processed_at
string error
string consumer_name
UUID correlation_id
UUID causation_id
datetime created_at
```

Recommended statuses:

```txt
pending
processing
processed
failed
dead
```

Recommended unique constraint when using one dispatcher:

```txt
UNIQUE(outbox_origin_id)
```

Recommended unique constraint when using multiple consumers:

```txt
UNIQUE(outbox_origin_id, consumer_name)
```

Notes:

```txt
inbox status means processing status
processed means the handler was executed
```

---

# Core relationships

Main relationships:

```txt
identity.organizations 1:N core.projects
identity.users 1:N identity.user_sessions
identity.users N:N identity.organizations through identity.organization_members
core.projects 1:N core.api_keys
core.projects 1:N ai.provider_credentials
core.projects 1:N ai.agents
ai.agents N:N knowledge.document_collections through knowledge.agent_collections
knowledge.document_collections 1:N knowledge.documents
knowledge.documents 1:N knowledge.document_chunks
ai.agents 1:N runtime.sessions
runtime.sessions 1:N runtime.messages
ai.agents 1:N tools.tools
core.projects 1:N metering.usage_events
billing.plans 1:N billing.subscriptions
billing.customers 1:N billing.subscriptions
observability.traces 1:N observability.trace_events
events.outbox_events 1:1 or 1:N events.inbox_events depending on consumer strategy
```

## Implementation note

When implementing SQLAlchemy models, every model must be placed in the correct module:

```txt
identity tables → src/modules/identity/infra/models.py
core tables → src/modules/core/infra/models.py
ai tables → src/modules/ai/infra/models.py
knowledge tables → src/modules/knowledge/infra/models.py
runtime tables → src/modules/runtime/infra/models.py
tools tables → src/modules/tools/infra/models.py
metering tables → src/modules/metering/infra/models.py
billing tables → src/modules/billing/infra/models.py
observability tables → src/modules/observability/infra/models.py
events tables → src/modules/events/infra/models.py
```

## Final rule

The schema is the module boundary in the database.

The module is the schema boundary in the code.

Every table must have a clear owner.

Every column must have a reason to exist.

Avoid generic tables without ownership.

Avoid JSON for data that should be queried often.

Keep high-volume tables simple, indexed, and easy to partition later.
