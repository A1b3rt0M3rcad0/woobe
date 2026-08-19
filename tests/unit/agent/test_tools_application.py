import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

import pytest

from modules.agent.domain.events import AgentDomainEvent

from modules.agent.application.dtos.tools_dtos import (
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
    TestToolInput as ToolTestInput,
    TestToolOutput as ToolTestOutput,
    UpdateToolInput,
    UpdateToolStatusInput,
)
from modules.agent.application.interfaces.ports import (
    ExecutionResult,
    SecretCipherPort,
    ToolExecutionPort,
)
from modules.agent.application.use_cases.tools_use_cases import (
    CreateSecretUseCase,
    CreateToolUseCase,
    DeleteToolUseCase,
    ExecuteToolUseCase,
    ListSecretsUseCase,
    ListToolsByAgentUseCase,
    ListToolsUseCase,
    TestToolUseCase as ToolTestUseCase,
    UpdateToolStatusUseCase,
    UpdateToolUseCase,
)
from modules.agent.domain.entities import Secret, Tool
from modules.agent.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType
from modules.agent.domain.errors import ToolNotFoundError
from modules.agent.application.interfaces.repositories import SecretRepository, ToolRepository


# ── Fakes ────────────────────────────────────────────────────────


class FakeToolRepository(ToolRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, Tool] = {}

    async def create(self, tool: Tool) -> Tool:
        now = datetime.now(timezone.utc)
        tool.created_at = now
        tool.updated_at = now
        self._store[tool.id] = tool
        return tool

    async def get_by_id(self, tool_id: UUID) -> Tool:
        if tool_id not in self._store:
            raise ToolNotFoundError(tool_id)
        return self._store[tool_id]

    async def list_by_project(self, project_id: UUID, status: str | None = None) -> list[Tool]:
        return [t for t in self._store.values() if t.project_id == project_id]

    async def list_by_agent(self, agent_id: UUID, status: str | None = None) -> list[Tool]:
        return [t for t in self._store.values() if t.agent_id == agent_id]

    async def paginate_by_project(self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None) -> list[Tool]:
        return []

    async def paginate_by_agent(self, agent_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None) -> list[Tool]:
        return []

    async def update(self, tool: Tool) -> Tool:
        tool.updated_at = datetime.now(timezone.utc)
        self._store[tool.id] = tool
        return tool

    async def delete(self, tool_id: UUID) -> None:
        self._store.pop(tool_id, None)


class FakeSecretRepository(SecretRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, Secret] = {}

    async def create(self, secret: Secret) -> Secret:
        now = datetime.now(timezone.utc)
        secret.created_at = now
        secret.updated_at = now
        self._store[secret.id] = secret
        return secret

    async def get_by_id(self, secret_id: UUID) -> Secret:
        if secret_id not in self._store:
            from modules.agent.domain.errors import SecretNotFoundError
            raise SecretNotFoundError(secret_id)
        return self._store[secret_id]

    async def get_by_name(self, project_id: UUID, name: str) -> Secret:
        for s in self._store.values():
            if s.project_id == project_id and s.name == name:
                return s
        from modules.agent.domain.errors import SecretNotFoundError
        raise SecretNotFoundError(name)

    async def list_by_project(self, project_id: UUID) -> list[Secret]:
        return [s for s in self._store.values() if s.project_id == project_id]

    async def paginate_by_project(self, project_id: UUID, *, limit: int = 50, cursor: str | None = None) -> list[Secret]:
        return []

    async def update(self, secret: Secret) -> Secret:
        secret.updated_at = datetime.now(timezone.utc)
        self._store[secret.id] = secret
        return secret

    async def delete(self, secret_id: UUID) -> None:
        self._store.pop(secret_id, None)


@dataclass
class FakeOutbox:
    events: list[AgentDomainEvent] = field(default_factory=list)

    async def write(self, event: AgentDomainEvent) -> None:
        self.events.append(event)


class FakeCipher(SecretCipherPort):
    async def encrypt(self, plaintext: str) -> str:
        return f"enc:{plaintext}"

    async def decrypt(self, ciphertext: str) -> str:
        return ciphertext.replace("enc:", "", 1)


class FakeToolExecutor(ToolExecutionPort):
    def __init__(self, result: ExecutionResult | None = None) -> None:
        self._result = result or ExecutionResult(success=True, output={"ok": True}, duration_ms=100)
        self.last_call: dict | None = None

    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        self.last_call = {
            "method": method,
            "url": url,
            "headers": headers,
            "body": body,
            "timeout_ms": timeout_ms,
        }
        return self._result


# ── DTO Compatibility Tests ──────────────────────────────────────


class TestToolsDTOs:
    def test_create_tool_input_fields(self):
        dto = CreateToolInput(
            project_id=uuid.uuid4(),
            name="test-tool",
            type=ToolType.API,
            risk_level=RiskLevel.MEDIUM,
        )
        assert dto.project_id is not None
        assert dto.name == "test-tool"
        assert dto.type == ToolType.API
        assert dto.risk_level == RiskLevel.MEDIUM

    def test_create_tool_output_fields(self):
        dto = CreateToolOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="test",
            description=None,
            type=ToolType.FUNCTION,
            config=None,
            input_schema=None,
            output_schema=None,
            risk_level=RiskLevel.LOW,
            timeout_ms=None,
            status=ToolStatus.ACTIVE,
        )
        assert dto.name == "test"
        assert dto.type == ToolType.FUNCTION

    def test_create_secret_input_fields(self):
        dto = CreateSecretInput(
            project_id=uuid.uuid4(),
            name="api-key",
            value="sk-123",
        )
        assert dto.name == "api-key"
        assert dto.type == SecretType.CUSTOM

    def test_create_secret_output_excludes_value(self):
        dto = CreateSecretOutput(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="api-key",
            type=SecretType.API_KEY,
            data=None,
        )
        assert not hasattr(dto, "value")
        assert not hasattr(dto, "encrypted_value")

    def test_execute_tool_input(self):
        dto = ExecuteToolInput(tool_id=uuid.uuid4())
        assert dto.tool_id is not None

    def test_execute_tool_output(self):
        dto = ExecuteToolOutput(success=True, output={"result": "ok"}, duration_ms=50)
        assert dto.success is True
        assert dto.output == {"result": "ok"}

    def test_test_tool_output(self):
        dto = ToolTestOutput(success=True, status_code=200, duration_ms=50)
        assert dto.success is True
        assert dto.status_code == 200


# ── Use Case Tests ───────────────────────────────────────────────


class TestCreateToolUseCase:
    @pytest.mark.asyncio
    async def test_create_tool_success(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        uc = CreateToolUseCase(repo, outbox)

        pid = uuid.uuid4()
        result = await uc.execute(CreateToolInput(
            project_id=pid,
            name="web-search",
            type=ToolType.API,
            config={"url": "https://api.example.com"},
        ))

        assert result.name == "web-search"
        assert result.project_id == pid
        assert result.status == ToolStatus.ACTIVE

        assert len(outbox.events) == 1
        assert outbox.events[0].event_type == "agent.tool.created.v1"
        assert outbox.events[0].payload["tool_id"] == str(result.id)

    @pytest.mark.asyncio
    async def test_create_tool_with_agent(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        uc = CreateToolUseCase(repo, outbox)

        pid = uuid.uuid4()
        aid = uuid.uuid4()
        result = await uc.execute(CreateToolInput(
            project_id=pid,
            agent_id=aid,
            name="agent-tool",
        ))

        assert result.agent_id == aid


class TestCreateSecretUseCase:
    @pytest.mark.asyncio
    async def test_create_secret_success(self):
        repo = FakeSecretRepository()
        outbox = FakeOutbox()
        cipher = FakeCipher()
        uc = CreateSecretUseCase(repo, outbox, cipher)

        pid = uuid.uuid4()
        result = await uc.execute(CreateSecretInput(
            project_id=pid,
            name="my-key",
            value="sk-real-secret",
            type=SecretType.API_KEY,
        ))

        assert result.name == "my-key"
        assert result.type == SecretType.API_KEY
        assert not hasattr(result, "value")
        assert not hasattr(result, "encrypted_value")

        saved = await repo.get_by_id(result.id)
        assert saved.encrypted_value == "enc:sk-real-secret"

        assert len(outbox.events) == 1
        assert outbox.events[0].event_type == "agent.secret.created.v1"
        assert "encrypted_value" not in outbox.events[0].payload


class TestUpdateToolUseCase:
    @pytest.mark.asyncio
    async def test_update_tool_name(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        uc = CreateToolUseCase(repo, outbox)
        uuc = UpdateToolUseCase(repo, outbox)

        created = await uc.execute(CreateToolInput(
            project_id=uuid.uuid4(),
            name="original",
        ))

        result = await uuc.execute(created.id, UpdateToolInput(name="renamed"))
        assert result.name == "renamed"

        assert len(outbox.events) == 2
        assert outbox.events[1].event_type == "agent.tool.updated.v1"


class TestUpdateToolStatusUseCase:
    @pytest.mark.asyncio
    async def test_update_status(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        uc = CreateToolUseCase(repo, outbox)
        suc = UpdateToolStatusUseCase(repo, outbox)

        created = await uc.execute(CreateToolInput(
            project_id=uuid.uuid4(),
            name="test",
        ))

        result = await suc.execute(created.id, UpdateToolStatusInput(status=ToolStatus.INACTIVE))
        assert result.status == ToolStatus.INACTIVE

        assert outbox.events[1].event_type == "agent.tool.status_changed.v1"
        assert outbox.events[1].payload["status"] == "inactive"


class TestDeleteToolUseCase:
    @pytest.mark.asyncio
    async def test_delete_tool(self, mocker):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        uc = CreateToolUseCase(repo, outbox)
        agent_repo = mocker.AsyncMock()
        agent_repo.list_by_project.return_value = []
        release_repo = mocker.AsyncMock()
        duc = DeleteToolUseCase(repo, agent_repo, release_repo)

        created = await uc.execute(CreateToolInput(
            project_id=uuid.uuid4(),
            name="to-delete",
        ))

        await duc.execute(DeleteToolInput(tool_id=created.id))
        with pytest.raises(ToolNotFoundError):
            await repo.get_by_id(created.id)


class TestExecuteToolUseCase:
    @pytest.mark.asyncio
    async def test_execute_active_tool(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        cnc = CreateToolUseCase(repo, outbox)

        created = await cnc.execute(CreateToolInput(
            project_id=uuid.uuid4(),
            name="http-bin",
            type=ToolType.API,
            config={"url": "https://httpbin.org/get", "method": "GET"},
        ))

        executor = FakeToolExecutor()
        uc = ExecuteToolUseCase(repo, executor)
        result = await uc.execute(ExecuteToolInput(tool_id=created.id))

        assert result.success is True
        assert executor.last_call is not None
        assert executor.last_call["method"] == "GET"
        assert "httpbin.org" in executor.last_call["url"]

    @pytest.mark.asyncio
    async def test_execute_inactive_tool_raises(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        cnc = CreateToolUseCase(repo, outbox)

        created = await cnc.execute(CreateToolInput(
            project_id=uuid.uuid4(),
            name="inactive-tool",
        ))

        store_tool = await repo.get_by_id(created.id)
        store_tool.status = ToolStatus.INACTIVE
        await repo.update(store_tool)

        executor = FakeToolExecutor()
        uc = ExecuteToolUseCase(repo, executor)
        with pytest.raises(ToolNotFoundError):
            await uc.execute(ExecuteToolInput(tool_id=created.id))

    @pytest.mark.asyncio
    async def test_execute_resolves_url_variables(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        cnc = CreateToolUseCase(repo, outbox)

        created = await cnc.execute(CreateToolInput(
            project_id=uuid.uuid4(),
            name="var-tool",
            type=ToolType.API,
            config={
                "url": "https://api.example.com/{{endpoint}}",
                "method": "GET",
                "variables": {"endpoint": "users"},
            },
        ))

        executor = FakeToolExecutor()
        uc = ExecuteToolUseCase(repo, executor)
        result = await uc.execute(ExecuteToolInput(
            tool_id=created.id,
            input_data={"endpoint": "items"},
        ))

        assert result.success is True
        assert executor.last_call["url"] == "https://api.example.com/items"


class TestTestToolUseCase:
    @pytest.mark.asyncio
    async def test_test_tool_executes(self):
        executor = FakeToolExecutor(ExecutionResult(
            success=True, status_code=200, body="ok", duration_ms=50,
        ))
        uc = ToolTestUseCase(executor)

        result = await uc.execute(ToolTestInput(
            config={"url": "https://example.com", "method": "GET"},
        ))

        assert result.success is True
        assert result.status_code == 200
        assert executor.last_call is not None
        assert executor.last_call["method"] == "GET"


class TestListToolsUseCase:
    @pytest.mark.asyncio
    async def test_list_by_project(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        cnc = CreateToolUseCase(repo, outbox)

        pid = uuid.uuid4()
        await cnc.execute(CreateToolInput(project_id=pid, name="a"))
        await cnc.execute(CreateToolInput(project_id=pid, name="b"))

        uc = ListToolsUseCase(repo)
        result = await uc.execute(ListToolsInput(project_id=pid))
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_empty_without_project(self):
        repo = FakeToolRepository()
        uc = ListToolsUseCase(repo)
        result = await uc.execute(ListToolsInput())
        assert result == []


class TestListToolsByAgentUseCase:
    @pytest.mark.asyncio
    async def test_list_by_agent(self):
        repo = FakeToolRepository()
        outbox = FakeOutbox()
        cnc = CreateToolUseCase(repo, outbox)

        aid = uuid.uuid4()
        await cnc.execute(CreateToolInput(project_id=uuid.uuid4(), agent_id=aid, name="tool1"))
        await cnc.execute(CreateToolInput(project_id=uuid.uuid4(), agent_id=aid, name="tool2"))

        uc = ListToolsByAgentUseCase(repo)
        result = await uc.execute(ListToolsByAgentInput(agent_id=aid))
        assert len(result) == 2


class TestListSecretsUseCase:
    @pytest.mark.asyncio
    async def test_list_by_project(self):
        repo = FakeSecretRepository()
        outbox = FakeOutbox()
        cipher = FakeCipher()
        cnc = CreateSecretUseCase(repo, outbox, cipher)

        pid = uuid.uuid4()
        await cnc.execute(CreateSecretInput(project_id=pid, name="k1", value="v1"))
        await cnc.execute(CreateSecretInput(project_id=pid, name="k2", value="v2"))

        uc = ListSecretsUseCase(repo)
        result = await uc.execute(ListSecretsInput(project_id=pid))
        assert len(result) == 2
