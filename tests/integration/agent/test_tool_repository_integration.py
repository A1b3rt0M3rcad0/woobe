from uuid import uuid4

import pytest

from modules.agent.domain.entities import Secret, Tool
from modules.agent.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType
from modules.agent.domain.errors import SecretNotFoundError, ToolNotFoundError
from modules.agent.application.interfaces.repositories import SecretRepository, ToolRepository


class FakeToolRepository(ToolRepository):
    def __init__(self) -> None:
        self._store: dict = {}

    async def create(self, tool: Tool) -> Tool:
        self._store[tool.id] = tool
        return tool

    async def get_by_id(self, tool_id) -> Tool:
        if tool_id not in self._store:
            raise ToolNotFoundError(tool_id)
        return self._store[tool_id]

    async def list_by_project(self, project_id, status=None):
        result = [t for t in self._store.values() if t.project_id == project_id]
        if status:
            status_val = status.value if hasattr(status, 'value') else status
            result = [t for t in result if (t.status.value if hasattr(t.status, 'value') else t.status) == status_val]
        return result

    async def list_by_agent(self, agent_id, status=None):
        return [t for t in self._store.values() if t.agent_id == agent_id]

    async def paginate_by_project(self, project_id, *, status=None, limit=50, cursor=None):
        return type("Page", (), {"items": [], "cursor": None, "next_cursor": None, "has_next": False, "total": 0})()

    async def paginate_by_agent(self, agent_id, *, status=None, limit=50, cursor=None):
        return type("Page", (), {"items": [], "cursor": None, "next_cursor": None, "has_next": False, "total": 0})()

    async def update(self, tool: Tool) -> Tool:
        self._store[tool.id] = tool
        return tool

    async def delete(self, tool_id) -> None:
        if tool_id not in self._store:
            raise ToolNotFoundError(tool_id)
        self._store.pop(tool_id, None)


class FakeSecretRepository(SecretRepository):
    def __init__(self) -> None:
        self._store: dict = {}

    async def create(self, secret: Secret) -> Secret:
        self._store[secret.id] = secret
        return secret

    async def get_by_id(self, secret_id) -> Secret:
        if secret_id not in self._store:
            raise SecretNotFoundError(secret_id)
        return self._store[secret_id]

    async def get_by_name(self, project_id, name) -> Secret:
        for s in self._store.values():
            if s.project_id == project_id and s.name == name:
                return s
        raise SecretNotFoundError(name)

    async def list_by_project(self, project_id):
        return [s for s in self._store.values() if s.project_id == project_id]

    async def paginate_by_project(self, project_id, *, limit=50, cursor=None):
        return type("Page", (), {"items": [], "cursor": None, "next_cursor": None, "has_next": False, "total": 0})()

    async def update(self, secret: Secret) -> Secret:
        self._store[secret.id] = secret
        return secret

    async def delete(self, secret_id) -> None:
        if secret_id not in self._store:
            raise SecretNotFoundError(secret_id)
        self._store.pop(secret_id, None)


@pytest.fixture
def tool_repo():
    return FakeToolRepository()


@pytest.fixture
def secret_repo():
    return FakeSecretRepository()


class TestToolRepositoryContract:

    async def test_create_and_get_by_id(self, tool_repo: FakeToolRepository):
        tool = Tool(
            id=uuid4(),
            project_id=uuid4(),
            name="test-tool",
            type=ToolType.FUNCTION,
            risk_level=RiskLevel.LOW,
            status=ToolStatus.ACTIVE,
        )
        created = await tool_repo.create(tool)
        assert created.id == tool.id

        fetched = await tool_repo.get_by_id(tool.id)
        assert fetched.name == "test-tool"
        assert fetched.type == ToolType.FUNCTION

    async def test_get_by_id_raises_not_found(self, tool_repo: FakeToolRepository):
        with pytest.raises(ToolNotFoundError):
            await tool_repo.get_by_id(uuid4())

    async def test_list_by_project(self, tool_repo: FakeToolRepository):
        pid = uuid4()
        t1 = Tool(id=uuid4(), project_id=pid, name="t1", type=ToolType.FUNCTION)
        t2 = Tool(id=uuid4(), project_id=pid, name="t2", type=ToolType.FUNCTION)
        t3 = Tool(id=uuid4(), project_id=uuid4(), name="t3", type=ToolType.FUNCTION)
        await tool_repo.create(t1)
        await tool_repo.create(t2)
        await tool_repo.create(t3)

        results = await tool_repo.list_by_project(pid)
        assert len(results) == 2

    async def test_list_by_project_filters_status(self, tool_repo: FakeToolRepository):
        pid = uuid4()
        t1 = Tool(id=uuid4(), project_id=pid, name="t1", type=ToolType.FUNCTION, status=ToolStatus.ACTIVE)
        t2 = Tool(id=uuid4(), project_id=pid, name="t2", type=ToolType.FUNCTION, status=ToolStatus.INACTIVE)
        await tool_repo.create(t1)
        await tool_repo.create(t2)

        results = await tool_repo.list_by_project(pid, status="inactive")
        assert len(results) == 1
        assert results[0].name == "t2"

    async def test_list_by_agent(self, tool_repo: FakeToolRepository):
        aid = uuid4()
        t1 = Tool(id=uuid4(), project_id=uuid4(), agent_id=aid, name="t1", type=ToolType.FUNCTION)
        t2 = Tool(id=uuid4(), project_id=uuid4(), agent_id=aid, name="t2", type=ToolType.FUNCTION)
        await tool_repo.create(t1)
        await tool_repo.create(t2)

        results = await tool_repo.list_by_agent(aid)
        assert len(results) == 2

    async def test_update(self, tool_repo: FakeToolRepository):
        tool = Tool(id=uuid4(), project_id=uuid4(), name="original", type=ToolType.FUNCTION)
        await tool_repo.create(tool)

        tool.name = "updated"
        updated = await tool_repo.update(tool)
        assert updated.name == "updated"

        fetched = await tool_repo.get_by_id(tool.id)
        assert fetched.name == "updated"

    async def test_delete(self, tool_repo: FakeToolRepository):
        tool = Tool(id=uuid4(), project_id=uuid4(), name="to-delete", type=ToolType.FUNCTION)
        await tool_repo.create(tool)
        await tool_repo.delete(tool.id)

        with pytest.raises(ToolNotFoundError):
            await tool_repo.get_by_id(tool.id)

    async def test_delete_raises_not_found(self, tool_repo: FakeToolRepository):
        with pytest.raises(ToolNotFoundError):
            await tool_repo.delete(uuid4())


class TestSecretRepositoryContract:

    async def test_create_and_get_by_id(self, secret_repo: FakeSecretRepository):
        secret = Secret(
            id=uuid4(),
            project_id=uuid4(),
            name="test-secret",
            type=SecretType.API_KEY,
            encrypted_value="enc:abc123",
        )
        created = await secret_repo.create(secret)
        assert created.id == secret.id

        fetched = await secret_repo.get_by_id(secret.id)
        assert fetched.name == "test-secret"
        assert fetched.type == SecretType.API_KEY

    async def test_get_by_id_raises_not_found(self, secret_repo: FakeSecretRepository):
        with pytest.raises(SecretNotFoundError):
            await secret_repo.get_by_id(uuid4())

    async def test_get_by_name(self, secret_repo: FakeSecretRepository):
        pid = uuid4()
        secret = Secret(id=uuid4(), project_id=pid, name="my-secret", type=SecretType.CUSTOM)
        await secret_repo.create(secret)

        fetched = await secret_repo.get_by_name(pid, "my-secret")
        assert fetched.name == "my-secret"

    async def test_get_by_name_raises_not_found(self, secret_repo: FakeSecretRepository):
        with pytest.raises(SecretNotFoundError):
            await secret_repo.get_by_name(uuid4(), "nonexistent")

    async def test_list_by_project(self, secret_repo: FakeSecretRepository):
        pid = uuid4()
        s1 = Secret(id=uuid4(), project_id=pid, name="s1", type=SecretType.CUSTOM)
        s2 = Secret(id=uuid4(), project_id=pid, name="s2", type=SecretType.CUSTOM)
        s3 = Secret(id=uuid4(), project_id=uuid4(), name="s3", type=SecretType.CUSTOM)
        await secret_repo.create(s1)
        await secret_repo.create(s2)
        await secret_repo.create(s3)

        results = await secret_repo.list_by_project(pid)
        assert len(results) == 2

    async def test_update(self, secret_repo: FakeSecretRepository):
        secret = Secret(id=uuid4(), project_id=uuid4(), name="original", type=SecretType.CUSTOM)
        await secret_repo.create(secret)

        secret.name = "updated"
        updated = await secret_repo.update(secret)
        assert updated.name == "updated"

        fetched = await secret_repo.get_by_id(secret.id)
        assert fetched.name == "updated"

    async def test_delete(self, secret_repo: FakeSecretRepository):
        secret = Secret(id=uuid4(), project_id=uuid4(), name="to-delete", type=SecretType.CUSTOM)
        await secret_repo.create(secret)
        await secret_repo.delete(secret.id)

        with pytest.raises(SecretNotFoundError):
            await secret_repo.get_by_id(secret.id)

    async def test_delete_raises_not_found(self, secret_repo: FakeSecretRepository):
        with pytest.raises(SecretNotFoundError):
            await secret_repo.delete(uuid4())


class TestMapperConsistency:

    def test_tool_mapper_roundtrip(self):
        from modules.agent.infra.database.mappers import model_to_tool, tool_to_model
        from modules.agent.infra.database.models import AgentToolModel

        tool = Tool(
            id=uuid4(),
            project_id=uuid4(),
            agent_id=uuid4(),
            name="roundtrip",
            description="test",
            type=ToolType.FUNCTION,
            config={"url": "http://example.com"},
            input_schema={"type": "object"},
            output_schema={"type": "string"},
            risk_level=RiskLevel.MEDIUM,
            timeout_ms=5000,
            status=ToolStatus.ACTIVE,
        )
        model = tool_to_model(tool)
        assert isinstance(model, AgentToolModel)
        assert model.name == "roundtrip"
        assert model.type == "function"

        entity = model_to_tool(model)
        assert entity.name == "roundtrip"
        assert entity.type == ToolType.FUNCTION
        assert entity.risk_level == RiskLevel.MEDIUM

    def test_secret_mapper_roundtrip(self):
        from modules.agent.infra.database.mappers import model_to_secret, secret_to_model
        from modules.agent.infra.database.models import AgentToolSecretModel

        secret = Secret(
            id=uuid4(),
            project_id=uuid4(),
            name="api-key",
            type=SecretType.API_KEY,
            encrypted_value="enc:secret123",
            data={"scope": "read"},
        )
        model = secret_to_model(secret)
        assert isinstance(model, AgentToolSecretModel)
        assert model.name == "api-key"
        assert model.type == "api_key"

        entity = model_to_secret(model)
        assert entity.name == "api-key"
        assert entity.type == SecretType.API_KEY
        assert entity.encrypted_value == "enc:secret123"


class TestModelMetadata:

    def test_agent_tool_model_schema(self):
        from modules.agent.infra.database.models import AgentToolModel

        assert AgentToolModel.__tablename__ == "tools"
        table_args = AgentToolModel.__table_args__
        schemas = [a for a in table_args if isinstance(a, dict) and a.get("schema") == "agent"]
        assert schemas, "AgentToolModel must have schema='agent'"

    def test_agent_tool_secret_model_schema(self):
        from modules.agent.infra.database.models import AgentToolSecretModel

        assert AgentToolSecretModel.__tablename__ == "tool_secrets"
        table_args = AgentToolSecretModel.__table_args__
        schemas = [a for a in table_args if isinstance(a, dict) and a.get("schema") == "agent"]
        assert schemas, "AgentToolSecretModel must have schema='agent'"

    def test_tool_model_no_cross_module_fk(self):
        from modules.agent.infra.database.models import AgentToolModel

        for col in AgentToolModel.__table__.columns:
            for fk in col.foreign_keys:
                assert fk.column.table.schema == "agent", (
                    f"AgentToolModel.{col.name} has cross-module FK to {fk.column.table.schema}"
                )

    def test_tool_secret_model_no_cross_module_fk(self):
        from modules.agent.infra.database.models import AgentToolSecretModel

        for col in AgentToolSecretModel.__table__.columns:
            for fk in col.foreign_keys:
                assert fk.column.table.schema == "agent", (
                    f"AgentToolSecretModel.{col.name} has cross-module FK to {fk.column.table.schema}"
                )

    def test_agent_tool_model_has_project_index(self):
        from modules.agent.infra.database.models import AgentToolModel

        table_args = AgentToolModel.__table_args__
        indexes = [a for a in table_args if hasattr(a, "name") and "project_id" in str(a.columns)]
        assert indexes, "AgentToolModel must have an index on project_id"

    def test_agent_tool_model_has_agent_index(self):
        from modules.agent.infra.database.models import AgentToolModel

        table_args = AgentToolModel.__table_args__
        indexes = [a for a in table_args if hasattr(a, "name") and "agent_id" in str(a.columns)]
        assert indexes, "AgentToolModel must have an index on agent_id"
