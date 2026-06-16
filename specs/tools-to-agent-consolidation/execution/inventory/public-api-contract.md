# Public API Contract — Agent Tools

## Target contract for `modules.agent` tool capabilities

### Domain interfaces (public contracts)

```python
# Repository interfaces (modules.agent.domain.repositories)
class ToolRepository(ABC):
    async def create(self, tool: Tool) -> Tool
    async def get_by_id(self, tool_id: UUID) -> Tool
    async def list_by_project(self, project_id: UUID, status: str | None = None) -> list[Tool]
    async def list_by_agent(self, agent_id: UUID, status: str | None = None) -> list[Tool]
    async def paginate_by_project(self, project_id: UUID, *, status=None, limit=50, cursor=None) -> CursorPage[Tool]
    async def paginate_by_agent(self, agent_id: UUID, *, status=None, limit=50, cursor=None) -> CursorPage[Tool]
    async def update(self, tool: Tool) -> Tool
    async def delete(self, tool_id: UUID) -> None

class SecretRepository(ABC):
    async def create(self, secret: Secret) -> Secret
    async def get_by_id(self, secret_id: UUID) -> Secret
    async def get_by_name(self, project_id: UUID, name: str) -> Secret
    async def list_by_project(self, project_id: UUID) -> list[Secret]
    async def paginate_by_project(self, project_id: UUID, *, limit=50, cursor=None) -> CursorPage[Secret]
    async def update(self, secret: Secret) -> Secret
    async def delete(self, secret_id: UUID) -> None

# Port interfaces (modules.agent.domain.ports) — already exist
class ToolExecutor(ABC):
    async def execute_tool(self, tool_id: UUID, input_data: dict) -> dict
    async def tool_to_openai_definition(self, tool_id: UUID) -> dict | None
```

### Supported use cases

| Use Case | Input | Output |
|---|---|---|
| CreateToolUseCase | CreateToolInput | CreateToolOutput |
| UpdateToolUseCase | tool_id, UpdateToolInput | CreateToolOutput |
| UpdateToolStatusUseCase | tool_id, UpdateToolStatusInput | CreateToolOutput |
| DeleteToolUseCase | DeleteToolInput | None |
| ExecuteToolUseCase | ExecuteToolInput | ExecuteToolOutput |
| TestToolUseCase | TestToolInput | TestToolOutput |
| ListToolsUseCase | ListToolsInput | list |
| ListToolsByAgentUseCase | ListToolsByAgentInput | list |
| CreateSecretUseCase | CreateSecretInput | CreateSecretOutput |
| ListSecretsUseCase | ListSecretsInput | list |

### HTTP API (preserved routes)

| Method | Path | Status |
|---|---|---|
| GET | `/tools` | Preserved |
| POST | `/tools` | Preserved |
| PATCH | `/tools/{tool_id}` | Preserved |
| PATCH | `/tools/{tool_id}/status` | Preserved |
| DELETE | `/tools/{tool_id}` | Preserved |
| POST | `/tools/test` | Preserved |
| POST | `/tools/execute` | Preserved |
| GET | `/agents/{agent_id}/tools` | Preserved |
| GET | `/secrets` | Preserved |
| POST | `/secrets` | Preserved |

### Events (produced)

| Event Type | Status |
|---|---|
| `tools.tool.created` | To be remapped to `agent.tool.created.v1` |
| `tools.tool.updated` | To be remapped to `agent.tool.updated.v1` |
| `tools.tool.status_changed` | To be remapped to `agent.tool.status_changed.v1` |
| `tools.secret.created` | To be remapped to `agent.secret.created.v1` |

### Events (consumed)

| Event Type | Status |
|---|---|
| `tools.tool.created` | Routing changed to agent inbox |
| `tools.tool.updated` | Routing changed to agent inbox |
| `tools.tool.status_changed` | Routing changed to agent inbox |
| `tools.secret.created` | Routing changed to agent inbox |

### AgentUnitOfWork additions

```python
class AgentUnitOfWork(UnitOfWork):
    @property
    def tools(self) -> SQLAlchemyToolRepository: ...
    @property
    def secrets(self) -> SQLAlchemySecretRepository: ...
```

### Authorization and security

- Tool and secret operations continue to use existing request adapter authorization
- Secrets never exposed in logs, events, responses, or error messages
- Encryption/decryption remains as internal utility (`shared.infra.crypto`)
