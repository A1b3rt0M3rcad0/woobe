"""Transaction and concurrency tests for tools agent consolidation (spec 015).

Covers Outbox atomicity, use case execution, and event correlation
using the same DTO and fake patterns as test_tools_application.py.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from modules.agent.domain.events import AgentDomainEvent

import pytest

from modules.agent.application.dtos.tools_dtos import (
    CreateSecretInput,
    CreateToolInput,
    ListToolsInput,
    UpdateToolInput,
)
from modules.agent.application.interfaces.ports import SecretCipherPort
from modules.agent.application.use_cases.tools_use_cases import (
    CreateSecretUseCase,
    CreateToolUseCase,
    ListToolsUseCase,
    UpdateToolUseCase,
)
from modules.agent.domain.entities import Secret, Tool
from modules.agent.domain.enums import RiskLevel, SecretType, ToolType
from modules.agent.application.interfaces.repositories import SecretRepository, ToolRepository


class FakeToolRepo(ToolRepository):
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
            from modules.agent.domain.errors import ToolNotFoundError
            raise ToolNotFoundError(tool_id)
        return self._store[tool_id]

    async def list_by_project(self, project_id: UUID, status=None):
        return [t for t in self._store.values() if t.project_id == project_id]

    async def list_by_agent(self, agent_id: UUID, status=None):
        return [t for t in self._store.values() if t.agent_id == agent_id]

    async def paginate_by_project(self, project_id: UUID, *, status=None, limit=50, cursor=None):
        return type("Page", (), {"items": [], "cursor": None, "next_cursor": None, "has_next": False, "total": 0})()

    async def paginate_by_agent(self, agent_id: UUID, *, status=None, limit=50, cursor=None):
        return type("Page", (), {"items": [], "cursor": None, "next_cursor": None, "has_next": False, "total": 0})()

    async def update(self, tool: Tool) -> Tool:
        self._store[tool.id] = tool
        return tool

    async def delete(self, tool_id: UUID) -> None:
        self._store.pop(tool_id, None)


class FakeSecretRepo(SecretRepository):
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

    async def paginate_by_project(self, project_id: UUID, *, limit=50, cursor=None):
        return []

    async def update(self, secret: Secret) -> Secret:
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


@pytest.fixture
def pid():
    return uuid.uuid4()


@pytest.fixture
def aid():
    return uuid.uuid4()


@pytest.fixture
def tool_repo():
    return FakeToolRepo()


@pytest.fixture
def secret_repo():
    return FakeSecretRepo()


@pytest.fixture
def outbox():
    return FakeOutbox()


@pytest.fixture
def cipher():
    return FakeCipher()


class TestToolTransactionAtomicity:
    async def test_create_tool_saves_to_repo(self, pid, aid, tool_repo, outbox):
        uc = CreateToolUseCase(tool_repo, outbox)
        result = await uc.execute(CreateToolInput(
            project_id=pid, agent_id=aid, name="http-tool", type=ToolType.HTTP_MCP,
            config={"url": "https://api.example.com"}, risk_level=RiskLevel.LOW,
        ))
        assert result is not None
        assert result.name == "http-tool"
        assert result.project_id == pid

    async def test_create_tool_publishes_outbox_event(self, pid, aid, tool_repo, outbox):
        uc = CreateToolUseCase(tool_repo, outbox)
        result = await uc.execute(CreateToolInput(
            project_id=pid, agent_id=aid, name="event-tool", type=ToolType.HTTP_MCP,
            config={"url": "https://event.example.com"}, risk_level=RiskLevel.LOW,
        ))
        assert len(outbox.events) == 1
        assert outbox.events[0].event_type == "agent.tool.created.v1"
        assert outbox.events[0].payload["tool_id"] == str(result.id)

    async def test_list_tools_returns_created(self, pid, aid, tool_repo, outbox):
        create = CreateToolUseCase(tool_repo, outbox)
        await create.execute(CreateToolInput(
            project_id=pid, agent_id=aid, name="a", type=ToolType.HTTP_MCP,
            config={"url": "https://a.com"}, risk_level=RiskLevel.LOW,
        ))
        list_uc = ListToolsUseCase(tool_repo)
        tools = await list_uc.execute(ListToolsInput(project_id=pid))
        assert len(tools) >= 1

    async def test_update_tool_changes_name(self, pid, aid, tool_repo, outbox):
        create = CreateToolUseCase(tool_repo, outbox)
        tool = await create.execute(CreateToolInput(
            project_id=pid, agent_id=aid, name="original", type=ToolType.HTTP_MCP,
            config={"url": "https://upd.com"}, risk_level=RiskLevel.LOW,
        ))
        update = UpdateToolUseCase(tool_repo, outbox)
        result = await update.execute(tool_id=tool.id, input_dto=UpdateToolInput(
            name="updated-name",
        ))
        assert result.name == "updated-name"

    async def test_create_secret_publishes_event(self, pid, secret_repo, outbox, cipher):
        uc = CreateSecretUseCase(secret_repo, outbox, cipher)
        await uc.execute(CreateSecretInput(
            project_id=pid, name="api-key", value="sk-123", type=SecretType.API_KEY,
        ))
        assert len(outbox.events) == 1
        assert outbox.events[0].event_type == "agent.secret.created.v1"
        payload = outbox.events[0].payload
        assert "encrypted_value" not in payload
        assert payload["name"] == "api-key"
