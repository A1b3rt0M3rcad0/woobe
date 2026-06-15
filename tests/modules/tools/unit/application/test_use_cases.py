from uuid import UUID, uuid4

import pytest

from modules.tools.domain.entities import Secret, Tool
from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType
from modules.tools.application.dtos import (
    CreateSecretInput,
    CreateSecretOutput,
    CreateToolInput,
    CreateToolOutput,
    DeleteToolInput,
    ExecuteToolInput,
    ExecuteToolOutput,
    ListSecretsInput,
    ListToolsByAgentInput,
    ListToolsInput,
    TestToolInput,
    TestToolOutput,
    UpdateToolInput,
    UpdateToolStatusInput,
)
from modules.tools.application.use_cases import (
    CreateSecretUseCase,
    CreateToolUseCase,
    DeleteToolUseCase,
    ExecuteToolUseCase,
    ListSecretsUseCase,
    ListToolsByAgentUseCase,
    ListToolsUseCase,
    TestToolUseCase,
    UpdateToolStatusUseCase,
    UpdateToolUseCase,
)


class TestCreateToolUseCase:
    @pytest.mark.asyncio
    async def test_execute_creates_tool_and_emits_event(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        use_case = CreateToolUseCase(repo, outbox)
        input_dto = CreateToolInput(
            project_id=uuid4(),
            name="test-tool",
            type=ToolType.API,
        )
        result = await use_case.execute(input_dto)
        assert isinstance(result, CreateToolOutput)
        assert result.name == "test-tool"
        assert result.type == ToolType.API
        assert len(repo.created) == 1
        assert len(outbox.events) == 1
        assert outbox.events[0]["event_type"] == "tools.tool.created"


class TestCreateSecretUseCase:
    @pytest.mark.asyncio
    async def test_execute_creates_secret_and_emits_event(self):
        repo = FakeSecretRepository()
        outbox = FakeOutbox()
        use_case = CreateSecretUseCase(repo, outbox, encryption_key="test-key-32-bytes-long!!")
        input_dto = CreateSecretInput(
            project_id=uuid4(),
            name="api-key",
            type=SecretType.API_KEY,
            value="sk-123",
        )
        result = await use_case.execute(input_dto)
        assert isinstance(result, CreateSecretOutput)
        assert result.name == "api-key"
        assert len(repo.created) == 1
        assert len(outbox.events) == 1
        assert outbox.events[0]["event_type"] == "tools.secret.created"


class TestUpdateToolUseCase:
    @pytest.mark.asyncio
    async def test_execute_updates_tool_name(self):
        tool_id = uuid4()
        repo = FakeToolRepository(seed=[Tool(id=tool_id, name="old", project_id=uuid4())])
        outbox = FakeOutbox()
        use_case = UpdateToolUseCase(repo, outbox)
        input_dto = UpdateToolInput(name="new-name")
        result = await use_case.execute(tool_id, input_dto)
        assert result.name == "new-name"
        assert repo.updated[0].name == "new-name"
        assert outbox.events[0]["event_type"] == "tools.tool.updated"


class TestUpdateToolStatusUseCase:
    @pytest.mark.asyncio
    async def test_execute_updates_status(self):
        tool_id = uuid4()
        repo = FakeToolRepository(seed=[Tool(id=tool_id, status=ToolStatus.ACTIVE, project_id=uuid4())])
        outbox = FakeOutbox()
        use_case = UpdateToolStatusUseCase(repo, outbox)
        input_dto = UpdateToolStatusInput(status=ToolStatus.INACTIVE)
        result = await use_case.execute(tool_id, input_dto)
        assert result.status == ToolStatus.INACTIVE
        assert outbox.events[0]["event_type"] == "tools.tool.status_changed"


class TestDeleteToolUseCase:
    @pytest.mark.asyncio
    async def test_execute_deletes_tool(self):
        tool_id = uuid4()
        repo = FakeToolRepository(seed=[Tool(id=tool_id)])
        use_case = DeleteToolUseCase(repo)
        await use_case.execute(DeleteToolInput(tool_id=tool_id))
        assert tool_id in repo.deleted


class TestListToolsUseCase:
    @pytest.mark.asyncio
    async def test_execute_returns_tools_by_project(self):
        project_id = uuid4()
        repo = FakeToolRepository(seed=[Tool(project_id=project_id)])
        use_case = ListToolsUseCase(repo)
        result = await use_case.execute(ListToolsInput(project_id=project_id))
        assert len(result) == 1


class TestListToolsByAgentUseCase:
    @pytest.mark.asyncio
    async def test_execute_returns_tools_by_agent(self):
        agent_id = uuid4()
        repo = FakeToolRepository(seed=[Tool(agent_id=agent_id)])
        use_case = ListToolsByAgentUseCase(repo)
        result = await use_case.execute(ListToolsByAgentInput(agent_id=agent_id))
        assert len(result) == 1


class TestListSecretsUseCase:
    @pytest.mark.asyncio
    async def test_execute_returns_secrets_by_project(self):
        project_id = uuid4()
        repo = FakeSecretRepository(seed=[Secret(project_id=project_id)])
        use_case = ListSecretsUseCase(repo)
        result = await use_case.execute(ListSecretsInput(project_id=project_id))
        assert len(result) == 1


class TestExecuteToolUseCase:
    @pytest.mark.asyncio
    async def test_execute_raises_error_for_inactive_tool(self):
        tool_id = uuid4()
        repo = FakeToolRepository(seed=[Tool(id=tool_id, status=ToolStatus.INACTIVE)])
        use_case = ExecuteToolUseCase(tool_repo=repo)
        from modules.tools.domain.errors import ToolNotFoundError
        with pytest.raises(ToolNotFoundError):
            await use_case.execute(ExecuteToolInput(tool_id=tool_id))


class TestTestToolUseCase:
    @pytest.mark.asyncio
    async def test_execute_returns_failure_for_invalid_config(self):
        use_case = TestToolUseCase()
        result = await use_case.execute(TestToolInput(config={}, input_data={}))
        assert isinstance(result, TestToolOutput)
        assert result.success is False


class FakeToolRepository:
    def __init__(self, seed: list[Tool] | None = None) -> None:
        self._store: dict[UUID, Tool] = {}
        if seed:
            for t in seed:
                self._store[t.id] = t
        self.created: list[Tool] = []
        self.updated: list[Tool] = []
        self.deleted: list[UUID] = []

    async def create(self, tool: Tool) -> Tool:
        tool.id = tool.id or uuid4()
        self._store[tool.id] = tool
        self.created.append(tool)
        return tool

    async def get_by_id(self, tool_id: UUID) -> Tool:
        return self._store.get(tool_id)

    async def list_by_project(self, project_id: UUID, status: str | None = None) -> list[Tool]:
        return [t for t in self._store.values() if t.project_id == project_id]

    async def list_by_agent(self, agent_id: UUID, status: str | None = None) -> list[Tool]:
        return [t for t in self._store.values() if t.agent_id == agent_id]

    async def paginate_by_project(self, project_id: UUID, **kwargs) -> list[Tool]:
        return []

    async def paginate_by_agent(self, agent_id: UUID, **kwargs) -> list[Tool]:
        return []

    async def update(self, tool: Tool) -> Tool:
        self._store[tool.id] = tool
        self.updated.append(tool)
        return tool

    async def delete(self, tool_id: UUID) -> None:
        self._store.pop(tool_id, None)
        self.deleted.append(tool_id)


class FakeSecretRepository:
    def __init__(self, seed: list[Secret] | None = None) -> None:
        self._store: dict[UUID, Secret] = {}
        if seed:
            for s in seed:
                self._store[s.id] = s
        self.created: list[Secret] = []

    async def create(self, secret: Secret) -> Secret:
        secret.id = secret.id or uuid4()
        self._store[secret.id] = secret
        self.created.append(secret)
        return secret

    async def get_by_id(self, secret_id: UUID) -> Secret:
        return self._store.get(secret_id)

    async def get_by_name(self, project_id: UUID, name: str) -> Secret:
        for s in self._store.values():
            if s.name == name and s.project_id == project_id:
                return s
        return None

    async def list_by_project(self, project_id: UUID) -> list[Secret]:
        return [s for s in self._store.values() if s.project_id == project_id]

    async def paginate_by_project(self, project_id: UUID, **kwargs) -> list[Secret]:
        return []

    async def update(self, secret: Secret) -> Secret:
        self._store[secret.id] = secret
        return secret

    async def delete(self, secret_id: UUID) -> None:
        self._store.pop(secret_id, None)


class FakeOutbox:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def write(self, **kwargs) -> None:
        self.events.append(kwargs)
