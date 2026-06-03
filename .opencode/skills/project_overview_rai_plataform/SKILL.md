---
name: project-overview-runtime-ai-platform
description: Defines what the project is, the product vision, the main problem it solves, target users, core modules, and expected MVP behavior.
---

# Project Overview — Runtime AI Platform

## What this project is

This project is a backend platform for running AI agents in production.

It is not only a chatbot.

It is not only a wrapper around an LLM provider.

It is a runtime layer that connects:

```txt
AI models
documents
RAG
tools
databases
sessions
messages
usage metering
billing
observability
event processing
```

The product allows a customer to create AI agents, connect those agents to knowledge sources and external tools, and expose them through a simple API.

The main idea is:

```txt
The customer should not need to build the full AI infrastructure from scratch.
The customer should create a project, configure an agent, connect data/tools, and call an API.
```

## Core value

The core value of the product is:

```txt
turning AI models into production-ready operational agents
```

The product reduces the engineering effort required to build:

```txt
RAG
session management
tool calling
provider credentials
fallbacks
cost tracking
logs
traces
usage limits
API keys
multi-project organization
```

The customer should be able to move from prototype to production faster.

## Main problem solved

Companies can call an LLM directly, but direct LLM calls do not solve the production problem.

A real AI agent needs:

```txt
documents
retrieval
sessions
tools
database access
external API calls
usage control
cost tracking
debugging
security
fallbacks
billing limits
```

This project provides that runtime layer.

## Target users

The primary users are:

```txt
SaaS companies
automation agencies
AI agencies
developers building AI products
teams that want AI agents connected to real data
companies using tools like n8n, Supabase, Postgres, MongoDB, MySQL or external APIs
```

The product is especially useful for users who want to build AI features without spending weeks creating their own agent infrastructure.

## Product positioning

The product can be described as:

```txt
An AI runtime platform for building production-ready agents with RAG, tools, sessions, usage tracking, and API access.
```

Short version:

```txt
A production runtime for AI agents.
```

Alternative positioning:

```txt
OpenAI gives the model.
This platform gives the operational agent runtime.
```

## MVP scope

The MVP should focus on the minimum set of features needed to prove the product can run agents in production-like conditions.

MVP features:

```txt
user authentication
organizations
projects
API keys
provider credentials
agents
document collections
document upload metadata
document chunks
pgvector embeddings
sessions
messages
tools
secrets
usage events
billing structure
outbox/inbox event flow
basic observability
```

The MVP does not need to solve everything at enterprise scale.

The MVP must prove that the user can:

```txt
create an account
create an organization
create a project
create an API key
connect provider credentials
create an agent
connect documents
connect tools
call the runtime API
receive an answer
store messages
track usage
```

## Main flow

The expected product flow is:

```txt
1. User signs up.
2. User creates or enters an organization.
3. User creates a project.
4. User creates an API key for the project.
5. User adds provider credentials, such as OpenAI.
6. User creates an agent.
7. User configures model, prompt, fallback, and session mode.
8. User uploads documents or connects a knowledge source.
9. System parses, chunks, embeds, and indexes knowledge.
10. User creates tools or HTTPMCP integrations.
11. External application calls the runtime endpoint.
12. Runtime loads project context, agent, session, knowledge, and tools.
13. Runtime calls the model.
14. Runtime stores messages and usage.
15. Runtime emits events through outbox/inbox when needed.
```

## Main runtime endpoint

The product should expose an API endpoint conceptually similar to:

```txt
POST /ask
```

or:

```txt
POST /v1/agents/{agent_id}/ask
```

The request should include:

```txt
message
session_id
user_id
tenant_id
metadata
```

The response should include:

```txt
answer
session_id
message_id
usage
sources when RAG is used
tool call summary when tools are used
```

## Modules

The system is organized as a modular monolith.

Each module has its own responsibility and its own database schema.

### identity

Responsible for:

```txt
users
organizations
organization members
sessions for dashboard authentication
organization invites
```

It answers:

```txt
who is the user?
which organization does the user belong to?
what role does the user have?
```

### core

Responsible for:

```txt
projects
API keys
project context
API authentication context
```

It answers:

```txt
which project is being accessed?
which API key is being used?
is the project active?
does the key have permission?
```

### ai

Responsible for:

```txt
agents
provider credentials
model configuration
fallback model configuration
agent settings
```

It answers:

```txt
which agent should run?
which model should be used?
which provider credential should be used?
what is the system prompt?
```

### knowledge

Responsible for:

```txt
document collections
agent collections
documents
document chunks
embeddings
pgvector search
```

It answers:

```txt
what knowledge can this agent use?
which documents are connected?
which chunks are relevant to the user question?
```

### runtime

Responsible for:

```txt
sessions
messages
agent execution
conversation state
ask flow
```

It answers:

```txt
what is the current conversation?
what messages should be stored?
what should the agent answer?
```

### tools

Responsible for:

```txt
tools
HTTPMCP
secrets
external integrations
input schemas
output schemas
risk level
timeouts
```

It answers:

```txt
what can the agent execute?
how does the agent call external systems?
which credentials are required?
```

### metering

Responsible for:

```txt
usage events
daily usage by project
daily usage by agent
tokens
requests
tool calls
vector queries
storage usage
estimated cost
```

It answers:

```txt
how much did the customer use?
how much did the agent cost?
which limits are being approached?
```

### billing

Responsible for:

```txt
plans
customers
subscriptions
payment events
commercial limits
```

It answers:

```txt
what plan does the customer have?
is the subscription active?
what limits should apply?
```

### observability

Responsible for:

```txt
traces
trace events
latency
errors
model used
fallback used
tool calls
RAG details
```

It answers:

```txt
what happened during execution?
why did the agent answer that way?
where did the request fail?
```

### events

Responsible for:

```txt
outbox events
inbox events
event publication
event reception
event dispatch
event retries
event dead-lettering
```

It answers:

```txt
what happened in one module?
which other modules need to react?
was the event published?
was the event processed?
```

## Communication between modules

Modules should avoid direct tight coupling.

Preferred communication:

```txt
module changes its own state
module emits event to outbox
event is published
event is received into inbox
dispatcher calls the correct handler
handler may update its own module
handler may emit another outbox event
```

The producer does not need to know who consumes the event.

The consumer decides whether the event matters.

## Outbox and inbox logic

Outbox means:

```txt
a module produced an event and it must be published
```

Inbox means:

```txt
an event was received and must be processed safely
```

Outbox ends when the event is published.

Inbox ends when the event is processed.

## Transaction rule

When a business operation needs to save data and create an event, both must happen in the same transaction.

Example:

```txt
create project
create outbox event project_created
commit both together
```

If one fails, both fail.

This avoids cases where the system changes state but loses the event.

## Database organization

Each module owns its own database schema.

Expected schemas:

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

Example tables:

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

The table name should not repeat the module prefix.

Correct:

```txt
core.projects
```

Incorrect:

```txt
core.core_projects
```

## Shared layer

The `shared` folder contains reusable generic code.

Examples:

```txt
BaseModel
BaseRepository
CursorPage
SessionManager
HttpRequest
HttpResponse
database session config
common errors
common dependencies
crypto utilities
```

The shared layer must not contain business rules from a specific module.

If something belongs to a module, it should stay inside the module.

## Repository pattern

Repositories are used to isolate persistence from business logic.

Rules:

```txt
repository interfaces belong to domain
concrete SQLAlchemy repositories belong to infra
services/use cases depend on repository interfaces
repositories receive the session from outside
repositories do not commit
repositories do not rollback
```

Commit and rollback are controlled by the SessionManager.

## SessionManager

The SessionManager controls transaction boundaries.

Rule:

```txt
one business operation = one transaction
```

If everything works:

```txt
commit
```

If something fails:

```txt
rollback
```

This is especially important for:

```txt
outbox
inbox
workers
use cases
multi-repository operations
```

## Workers

Workers are responsible for background processing.

Expected workers:

```txt
outbox publisher worker
inbox consumer worker
inbox dispatcher worker
document ingestion worker
embedding worker
usage aggregation worker
```

Workers should not contain the main business rules.

Workers should call services/use cases.

## MVP technical priorities

The MVP should prioritize:

```txt
correct modular structure
clear database schemas
transaction safety
API key authentication
agent creation
basic runtime execution
basic RAG
basic tools
usage recording
event propagation
simple billing structure
```

Avoid premature complexity.

Do not over-engineer distributed systems before product validation.

## Things that should not be overbuilt at MVP

Do not overbuild:

```txt
complex RBAC
enterprise SSO
multi-region
advanced tracing
custom workflow engine
complex billing engine
full marketplace
full visual builder
large-scale sharding
```

The MVP should prove the runtime value first.

## Expected final direction

The long-term product can evolve into:

```txt
AI runtime platform
agent infrastructure layer
RAG + tools + sessions + metering platform
production layer for AI agents
```

At scale, the system may later separate:

```txt
trace events into analytical storage
vector search into dedicated vector DB
large payloads into object storage
billing into stronger isolation
enterprise tenants into dedicated infrastructure
```

But the initial architecture must remain simple enough to build quickly.

## Final product summary

This project is a modular AI runtime platform that lets customers create production-ready AI agents connected to documents, tools, sessions, and external systems.

The platform provides the missing operational layer between raw AI models and real production applications.

The core promise is:

```txt
build and run AI agents in production without rebuilding all the infrastructure yourself
```
