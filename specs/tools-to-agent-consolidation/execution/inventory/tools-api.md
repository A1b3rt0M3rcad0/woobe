# Tools Module — API Inventory

Router prefix: `/tools` (registered from `src/modules/tools/presentation/routes.py`)

## Routes

| Method | Path | Handler | Status Codes | Description |
|---|---|---|---|---|
| GET | `/tools` | `list_tools` | 200 | List all tools (project context in request) |
| POST | `/tools` | `create_tool` | 201 | Create a new tool |
| PATCH | `/tools/{tool_id}` | `update_tool` | 200 | Update tool by ID |
| PATCH | `/tools/{tool_id}/status` | `update_tool_status` | 200 | Update tool status |
| DELETE | `/tools/{tool_id}` | `delete_tool` | 204 | Delete tool by ID |
| POST | `/tools/test` | `test_tool` | 200 | Test tool configuration |
| POST | `/tools/execute` | `execute_tool` | 200 | Execute a tool |
| GET | `/agents/{agent_id}/tools` | `list_tools_by_agent` | 200 | List tools by agent |
| GET | `/secrets` | `list_secrets` | 200 | List secrets (project context) |
| POST | `/secrets` | `create_secret` | 201 | Create a new secret |

## Request schemas

| Schema | Used By | Fields |
|---|---|---|
| `CreateToolRequest` | POST `/tools` | project_id, agent_id?, name, description?, type, config?, input_schema?, output_schema?, risk_level?, timeout_ms? |
| `UpdateToolRequest` | PATCH `/tools/{tool_id}` | name?, description?, agent_id?, config?, input_schema?, output_schema?, risk_level?, timeout_ms? |
| `UpdateToolStatusRequest` | PATCH `/tools/{tool_id}/status` | status |
| `TestToolRequest` | POST `/tools/test` | config, input_data? |
| `ExecuteToolRequest` | POST `/tools/execute` | tool_id, input_data?, agent_id? |
| `CreateSecretRequest` | POST `/secrets` | project_id, name, type?, value |

## Response schemas

| Schema | Used By |
|---|---|
| `ToolResponse` | GET/POST/PATCH `/tools*` |
| `TestToolResponse` | POST `/tools/test` |
| `ExecuteToolResponse` | POST `/tools/execute` |
| `SecretResponse` | GET/POST `/secrets` |

## Route registration

Router is exposed via `routes.router` and must be included in the FastAPI app with `include_router(router)`.

Detected via: `test_api_routes_registered.py:14` — `"tools": "/tools"`

## Authentication/Authorization

All routes use `request_adapter` wrapper that extracts auth context from `FastAPIRequest`. No explicit per-route auth decorators visible in routes.py.

Executed: `Select-String -Pattern "/tools|/agents/\{agent_id\}/tools|/secrets" -Path "src/**/*.py","tests/**/*.py"`
Exit code: 0
