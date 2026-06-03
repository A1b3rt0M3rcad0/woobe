---
name: frontend-mvp-functional-requirements
description: Defines everything the frontend MVP must have to operate the AI runtime platform, including authentication, projects, agents, credentials, knowledge, tools, playground, usage, billing, and observability.
---

# Frontend MVP Functional Requirements

## Objective

Define what the frontend must include for the ProjectRAI MVP to be functional.

This skill is focused on product screens, user flows, frontend structure, and minimum UI requirements.

It does not define backend implementation, database tables, or visual design in detail.

The goal is:

```txt
a user can create an account, configure an AI agent, connect knowledge/tools, test it in a playground, generate an API key, and understand usage.
```

## Product goal of the frontend

The frontend must make the backend usable by a real customer.

The backend provides:

```txt
projects
API keys
agents
provider credentials
documents
tools
runtime /ask
usage
billing
observability
```

The frontend must expose those capabilities in a simple dashboard.

The MVP frontend should not try to be a full visual workflow builder.

It should be a practical control panel for configuring and testing AI agents.

## Main user journey

The MVP user journey is:

```txt
1. User creates account or logs in.
2. User creates or enters an organization.
3. User creates a project.
4. User adds provider credentials.
5. User creates an agent.
6. User configures model, prompt, fallback, and session mode.
7. User optionally uploads documents or creates a knowledge collection.
8. User optionally creates tools.
9. User tests the agent in the playground.
10. User creates an API key.
11. User copies integration instructions.
12. User checks usage, cost, logs/traces, and billing status.
```

The MVP is successful when this flow works end-to-end.

## Frontend modules

The frontend should be organized around these product areas:

```txt
auth
organization
projects
api_keys
agents
provider_credentials
knowledge
tools
playground
runtime_history
usage
billing
observability
settings
```

## Required pages

Minimum pages for MVP:

```txt
/login
/register
/dashboard
/projects
/projects/:projectId
/projects/:projectId/api-keys
/projects/:projectId/agents
/projects/:projectId/agents/new
/projects/:projectId/agents/:agentId
/projects/:projectId/agents/:agentId/playground
/projects/:projectId/knowledge
/projects/:projectId/tools
/projects/:projectId/usage
/projects/:projectId/traces
/billing
/settings
```

If using a nested dashboard layout, the routes can be adapted, but the same functional areas must exist.

## Global layout

The authenticated dashboard should have:

```txt
sidebar navigation
current organization selector
current project selector
user menu
billing/status indicator
environment/status indicator
main content area
```

Sidebar items:

```txt
Overview
Projects
Agents
Knowledge
Tools
Playground
API Keys
Usage
Traces
Billing
Settings
```

For MVP, navigation can be project-scoped after a project is selected.

## Authentication UI

Required screens:

```txt
login
register
logout
current user menu
```

Login form fields:

```txt
email
password
```

Register form fields:

```txt
email
password
organization_name
```

After register:

```txt
create user
create organization
create owner membership
redirect to dashboard or project creation
```

MVP does not need:

```txt
SSO
OAuth
passwordless login
2FA
enterprise identity
```

## Organization UI

The frontend must show the current organization.

Minimum features:

```txt
view organization name
view current user role
list organization members
invite member
accept invite if supported
```

For MVP, member management can be simple.

Roles:

```txt
owner
admin
developer
viewer
```

Only owner/admin should see member invite actions.

## Project UI

The project is the main operational container.

Required screens:

```txt
project list
create project
project detail
project settings
```

Project list should show:

```txt
name
slug
status
created_at
```

Create project form:

```txt
name
slug optional
```

Project detail should show:

```txt
agents count
documents count
api keys count
usage summary
latest activity
```

Project settings should allow:

```txt
rename project
change status if allowed
delete/disable project if allowed
```

## API Keys UI

API keys are required for external integration.

Required features:

```txt
list API keys
create API key
revoke API key
copy key once
show key prefix
show scopes
show status
show last_used_at
```

Create API key form:

```txt
name
scopes
expires_at optional
```

Scopes MVP:

```txt
ask:write
documents:read
documents:write
agents:read
tools:read
usage:read
admin
```

Important UX rule:

```txt
the raw API key is shown only once after creation
```

The UI must clearly warn:

```txt
Copy this key now. You will not be able to see it again.
```

## Provider Credentials UI

Provider credentials allow BYOK.

Required features:

```txt
list provider credentials
create provider credential
validate credential if endpoint exists
disable/delete credential
```

Create credential form:

```txt
provider
name
secret/api_key
```

Supported providers for MVP:

```txt
openai
anthropic optional
google optional
custom optional
```

The frontend should never show the raw secret after save.

Display:

```txt
provider
name
status
last_validated_at
created_at
```

## Agents UI

Agents are the central product object.

Required screens:

```txt
agents list
create agent
agent detail/edit
agent playground
```

Agents list should show:

```txt
name
model
provider
status
session_mode
created_at
updated_at
```

Create/edit agent form should include:

```txt
name
description
type
system_prompt
provider
model
provider_credential_id
fallback_provider
fallback_model
fallback_credential_id
temperature
max_output_tokens
session_mode
status
settings
```

Recommended session modes:

```txt
managed
external
stateless
```

Agent settings should be practical, not overloaded.

Minimum advanced settings:

```txt
temperature
max_output_tokens
fallback model
session mode
```

Do not overbuild:

```txt
visual agent graph
workflow builder
multi-agent orchestration UI
complex memory policies
```

## Agent configuration UX

The agent edit page should have tabs:

```txt
General
Prompt
Model
Knowledge
Tools
Playground
API
```

### General tab

Fields:

```txt
name
description
status
type
```

### Prompt tab

Fields:

```txt
system_prompt
```

Include:

```txt
save button
reset/discard button
```

Optional helpful features:

```txt
prompt preview
character/token estimate
```

### Model tab

Fields:

```txt
provider
model
credential
temperature
max_output_tokens
fallback provider
fallback model
fallback credential
```

### Knowledge tab

Allow linking collections to the agent.

Actions:

```txt
attach collection
detach collection
view collection documents
```

### Tools tab

Allow linking or viewing tools available to the agent.

Actions:

```txt
create tool
edit tool
disable tool
```

### API tab

Show integration instructions.

Include:

```txt
endpoint URL
required headers
example curl
example JavaScript fetch
example Python request
agent_id
project_id
```

## Knowledge UI

Knowledge handles document collections and documents.

Required screens:

```txt
collections list
collection detail
document upload
document processing status
document chunks preview optional
```

Collection list should show:

```txt
name
description
status
documents_count
created_at
```

Create collection form:

```txt
name
description
```

Document upload form:

```txt
collection_id
file
title optional
```

Document list should show:

```txt
title
file_name
content_type
size_bytes
status
chunk_count
page_count
indexed_at
error
```

Document statuses:

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

The UI must clearly show failed document processing.

Minimum actions:

```txt
upload document
delete document
retry processing if failed
view metadata
```

MVP does not need:

```txt
advanced document editor
manual chunk editor
visual embedding explorer
```

## Tools UI

Tools allow agents to call external systems.

Required screens:

```txt
tools list
create tool
edit tool
test tool
secrets list
create secret
```

Tool fields:

```txt
name
description
type
config
input_schema
output_schema
risk_level
timeout_ms
status
```

MVP tool type:

```txt
http_mcp
```

Risk levels:

```txt
read_only
write
destructive
restricted
```

Tool config for HTTPMCP should support:

```txt
method
url
headers
auth_type
secret_ref
body_template
query_params
```

Secrets UI fields:

```txt
name
type
encrypted_value input
metadata optional
```

Raw secret must not be displayed after saving.

Tool test UI should allow:

```txt
input JSON
run test
show response status
show response body
show latency
show error if failed
```

## Playground UI

The playground is mandatory for MVP.

It is where the user tests the agent before integrating.

Required route:

```txt
/projects/:projectId/agents/:agentId/playground
```

The playground must include:

```txt
chat interface
message input
send button
session selector or session reset
show assistant response
show loading state
show error state
show usage summary
show retrieved sources when RAG is used
show tool calls when tools are used
show latency
show model used
show fallback used
```

Minimum request settings:

```txt
message
session_id optional
tenant_id optional
user_id optional
metadata optional
```

Controls:

```txt
new session
clear chat
copy response
copy request payload
copy API example
```

The playground should expose enough debug information to make the product credible.

Debug panel:

```txt
request payload
response payload
usage
sources
tool calls
trace id if available
```

The playground must support the three session modes:

```txt
managed = keep chat history
external = allow user to pass external_session_id
stateless = send message without stored conversation
```

## Runtime history UI

The frontend should show recent sessions and messages.

Minimum screens:

```txt
sessions list
session detail
messages list
```

Session list columns:

```txt
external_session_id
agent_id
tenant_id
user_id
status
last_message_at
created_at
```

Message list columns:

```txt
role
content preview
input_tokens
output_tokens
cost_usd
created_at
```

This can be simple for MVP.

## Usage UI

Usage lets the customer understand consumption.

Required screens:

```txt
usage overview
usage by project
usage by agent
usage events list optional
```

Metrics:

```txt
requests
input_tokens
output_tokens
embedding_tokens
tool_calls
vector_queries
storage_mb
estimated_cost_usd
```

Filters:

```txt
date range
project
agent
```

Display:

```txt
daily usage chart
summary cards
usage table
```

For MVP, charts can be simple.

No need for advanced analytics.

## Billing UI

Billing should be functional but simple.

Required screens:

```txt
current plan
subscription status
usage limits
payment/customer status
plan list
```

Display:

```txt
plan name
billing interval
price
status
current_period_start
current_period_end
limits
```

Actions:

```txt
upgrade/downgrade placeholder
open billing portal if available
contact sales placeholder
```

MVP can support manual billing status if payment integration is not complete.

## Observability / Traces UI

Observability is important for debugging.

Required screens:

```txt
traces list
trace detail
```

Traces list should show:

```txt
trace_id
agent
session
status
started_at
total_latency_ms
total_cost_usd
provider
model
fallback_used
error
```

Trace detail should show:

```txt
summary
timeline of events
RAG events
LLM events
tool call events
errors
payload references
```

Trace events should show:

```txt
event_type
created_at
latency_ms
cost_usd
payload preview
payload_ref
```

For MVP, trace details can be read-only.

## Dashboard overview

The main dashboard should show:

```txt
current organization
current project
number of agents
number of documents
number of API keys
usage this month
estimated cost this month
recent traces
recent sessions
quick actions
```

Quick actions:

```txt
create agent
upload document
open playground
create API key
create tool
```

## Settings UI

Settings should include:

```txt
organization settings
project settings
user settings
danger zone
```

User settings:

```txt
email
password change optional
logout
```

Organization settings:

```txt
name
slug
members
invites
```

Project settings:

```txt
name
slug
status
metadata optional
```

Danger zone:

```txt
revoke API key
delete project
disable agent
```

## Frontend permissions

The frontend should hide or disable actions based on role.

Roles:

```txt
owner
admin
developer
viewer
```

Basic permissions:

```txt
owner = everything
admin = manage organization/project/resources
developer = manage projects, agents, knowledge, tools, api keys
viewer = read-only
```

The backend must still enforce permissions.

Frontend permission checks are only for UX.

## Error states

Every main screen must handle:

```txt
loading
empty state
error state
success state
validation errors
permission denied
not found
```

Empty state examples:

```txt
No agents yet. Create your first agent.
No documents yet. Upload a document.
No API keys yet. Create an API key.
No traces yet. Run the playground.
```

## API integration requirements

The frontend should be built around API clients.

Recommended organization:

```txt
src/
  app/
  components/
  features/
    auth/
    projects/
    api-keys/
    agents/
    knowledge/
    tools/
    playground/
    usage/
    billing/
    traces/
  lib/
    api/
    auth/
    query/
    formatters/
```

API clients should be separated by feature:

```txt
authApi
projectsApi
apiKeysApi
agentsApi
knowledgeApi
toolsApi
runtimeApi
usageApi
billingApi
tracesApi
```

## Frontend state management

For MVP, prefer simple state.

Separate:

```txt
server state = API data
client state = selected project, UI tabs, modals, playground draft
auth state = current user/session
```

Do not overbuild global state.

## Forms

Forms should be strongly validated.

Important forms:

```txt
register
login
create project
create API key
create provider credential
create agent
edit agent
create collection
upload document
create tool
create secret
playground request
```

Each form should have:

```txt
loading state
validation errors
submit disabled during request
success feedback
clear error messages
```

## Security UX

Frontend must not display raw secrets after creation.

This applies to:

```txt
API keys
provider credentials
tool secrets
refresh tokens
internal secrets
```

API key creation should show the raw key only once.

Provider credential creation should never show the raw secret after save.

Secret creation should never show the raw value after save.

## MVP integration examples

The API tab for each agent should include copyable examples.

Example curl:

```txt
curl -X POST https://api.example.com/v1/agents/{agent_id}/ask \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "session_id": "user-123"
  }'
```

Example JavaScript:

```txt
await fetch("/v1/agents/{agent_id}/ask", {
  method: "POST",
  headers: {
    "Authorization": "Bearer <API_KEY>",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    message: "Hello",
    session_id: "user-123"
  })
})
```

Example Python:

```txt
import requests

requests.post(
    "https://api.example.com/v1/agents/{agent_id}/ask",
    headers={"Authorization": "Bearer <API_KEY>"},
    json={"message": "Hello", "session_id": "user-123"}
)
```

## MVP must-have checklist

The frontend MVP is only complete if the user can:

```txt
register
login
create organization
create project
create API key
create provider credential
create agent
edit agent prompt/model/settings
create document collection
upload document
see document processing status
attach collection to agent
create tool
create secret
test tool
open playground
send message to agent
see answer
see sources when RAG is used
see tool calls when tools are used
see usage
see traces
see billing/plan status
copy API integration example
```

## What not to build in MVP

Do not build yet:

```txt
visual workflow builder
drag-and-drop agent graph
multi-agent orchestration UI
marketplace
advanced team permissions
enterprise SSO
custom dashboards
advanced analytics
multi-region controls
white-label frontend
complex onboarding wizard
```

## Recommended MVP priority order

Build in this order:

```txt
1. Auth screens
2. Organization/project shell
3. Project list and create project
4. API keys
5. Provider credentials
6. Agents list/create/edit
7. Playground
8. Knowledge collections/documents
9. Tools/secrets
10. Usage
11. Traces
12. Billing
13. Settings
```

The most important MVP screen is:

```txt
Agent Playground
```

Because it proves the platform works.

## Final frontend goal

The MVP frontend must make the product usable without manual database edits or raw API calls.

The user should be able to configure and test a production-ready AI agent from the dashboard.

The core promise of the frontend is:

```txt
create agent
connect model
connect knowledge
connect tools
test in playground
copy API key
integrate in production
```
