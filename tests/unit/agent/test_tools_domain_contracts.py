import uuid
from datetime import datetime, timezone

from modules.agent.domain.entities import Secret, Tool
from modules.agent.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType
from modules.agent.domain.errors import (
    DuplicateSecretError,
    SecretNotFoundError,
    ToolNotFoundError,
)
from modules.agent.domain.events import (
    AgentSecretCreatedV1,
    AgentToolCreatedV1,
    AgentToolStatusChangedV1,
    AgentToolUpdatedV1,
)
from modules.agent.application.interfaces.repositories import SecretRepository, ToolRepository


class TestToolEntity:
    def test_defaults(self):
        t = Tool()
        assert isinstance(t.id, uuid.UUID)
        assert t.project_id is None
        assert t.agent_id is None
        assert t.name == ""
        assert t.description is None
        assert t.type == ToolType.FUNCTION
        assert t.config is None
        assert t.input_schema is None
        assert t.output_schema is None
        assert t.risk_level == RiskLevel.LOW
        assert t.timeout_ms is None
        assert t.status == ToolStatus.ACTIVE
        assert t.created_at is None
        assert t.updated_at is None

    def test_custom_values(self):
        now = datetime.now(timezone.utc)
        tid = uuid.uuid4()
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        t = Tool(
            id=tid,
            project_id=pid,
            agent_id=aid,
            name="search-tool",
            description="Searches the web",
            type=ToolType.API,
            config={"url": "https://api.example.com"},
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            risk_level=RiskLevel.MEDIUM,
            timeout_ms=5000,
            status=ToolStatus.INACTIVE,
            created_at=now,
            updated_at=now,
        )
        assert t.id == tid
        assert t.project_id == pid
        assert t.agent_id == aid
        assert t.name == "search-tool"
        assert t.description == "Searches the web"
        assert t.type == ToolType.API
        assert t.config == {"url": "https://api.example.com"}
        assert t.input_schema == {"type": "object", "properties": {}}
        assert t.output_schema == {"type": "object"}
        assert t.risk_level == RiskLevel.MEDIUM
        assert t.timeout_ms == 5000
        assert t.status == ToolStatus.INACTIVE
        assert t.created_at == now
        assert t.updated_at == now

    def test_uuid_generation(self):
        t1 = Tool()
        t2 = Tool()
        assert t1.id != t2.id


class TestSecretEntity:
    def test_defaults(self):
        s = Secret()
        assert isinstance(s.id, uuid.UUID)
        assert s.project_id is None
        assert s.name == ""
        assert s.type == SecretType.CUSTOM
        assert s.encrypted_value == ""
        assert s.data is None
        assert s.created_at is None
        assert s.updated_at is None

    def test_custom_values(self):
        now = datetime.now(timezone.utc)
        sid = uuid.uuid4()
        pid = uuid.uuid4()
        s = Secret(
            id=sid,
            project_id=pid,
            name="my-api-key",
            type=SecretType.API_KEY,
            encrypted_value="enc:abc123",
            data={"usage": "openai"},
            created_at=now,
            updated_at=now,
        )
        assert s.id == sid
        assert s.project_id == pid
        assert s.name == "my-api-key"
        assert s.type == SecretType.API_KEY
        assert s.encrypted_value == "enc:abc123"
        assert s.data == {"usage": "openai"}
        assert s.created_at == now
        assert s.updated_at == now

    def test_uuid_generation(self):
        s1 = Secret()
        s2 = Secret()
        assert s1.id != s2.id


class TestToolEnums:
    def test_tool_type_values(self):
        assert ToolType.FUNCTION == "function"
        assert ToolType.HTTP_MCP == "http_mcp"
        assert ToolType.API == "api"
        assert ToolType.CUSTOM == "custom"

    def test_risk_level_values(self):
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"

    def test_secret_type_values(self):
        assert SecretType.API_KEY == "api_key"
        assert SecretType.CUSTOM == "custom"

    def test_tool_status_values(self):
        assert ToolStatus.ACTIVE == "active"
        assert ToolStatus.INACTIVE == "inactive"


class TestToolErrors:
    def test_tool_not_found_error(self):
        tid = uuid.uuid4()
        err = ToolNotFoundError(tid)
        assert err.tool_id == tid
        assert str(tid) in str(err)

    def test_secret_not_found_error(self):
        sid = uuid.uuid4()
        err = SecretNotFoundError(sid)
        assert err.secret_id == sid

    def test_duplicate_secret_error(self):
        pid = uuid.uuid4()
        err = DuplicateSecretError("my-key", pid)
        assert err.name == "my-key"
        assert err.project_id == pid


class TestToolEvents:
    def test_tool_created_event(self):
        tid = uuid.uuid4()
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        event = AgentToolCreatedV1.create(
            tool_id=tid,
            project_id=pid,
            agent_id=aid,
            payload={},
        )
        assert event.event_type == "agent.tool.created.v1"
        assert event.payload["tool_id"] == str(tid)
        assert event.payload["project_id"] == str(pid)
        assert event.payload["agent_id"] == str(aid)
        assert event.idempotency_key

    def test_tool_updated_event(self):
        tid = uuid.uuid4()
        event = AgentToolUpdatedV1.create(
            tool_id=tid,
            payload={"name": "renamed"},
        )
        assert event.event_type == "agent.tool.updated.v1"
        assert event.payload["tool_id"] == str(tid)
        assert event.payload["name"] == "renamed"

    def test_tool_status_changed_event(self):
        tid = uuid.uuid4()
        event = AgentToolStatusChangedV1.create(
            tool_id=tid,
            status="inactive",
        )
        assert event.event_type == "agent.tool.status_changed.v1"
        assert event.payload["status"] == "inactive"

    def test_secret_created_event(self):
        sid = uuid.uuid4()
        pid = uuid.uuid4()
        event = AgentSecretCreatedV1.create(
            secret_id=sid,
            project_id=pid,
            name="my-key",
            secret_type="api_key",
        )
        assert event.event_type == "agent.secret.created.v1"
        assert event.payload["name"] == "my-key"
        assert "encrypted_value" not in event.payload

    def test_secret_no_plaintext_in_payload(self):
        sid = uuid.uuid4()
        pid = uuid.uuid4()
        event = AgentSecretCreatedV1.create(
            secret_id=sid,
            project_id=pid,
            name="my-key",
            secret_type="api_key",
        )
        payload_str = str(event.payload)
        assert "encrypted_value" not in payload_str
        assert "secret" not in payload_str.lower() or "encrypted" not in payload_str


class TestToolRepositories:
    def test_tool_repository_is_abstract(self):
        import inspect as _insp
        assert _insp.isabstract(ToolRepository)

    def test_tool_repository_has_expected_methods(self):
        expected = ["create", "get_by_id", "list_by_project", "list_by_agent",
                     "paginate_by_project", "paginate_by_agent", "update", "delete"]
        for method in expected:
            assert hasattr(ToolRepository, method)

    def test_secret_repository_is_abstract(self):
        import inspect as _insp
        assert _insp.isabstract(SecretRepository)

    def test_secret_repository_has_expected_methods(self):
        expected = ["create", "get_by_id", "get_by_name", "list_by_project",
                     "paginate_by_project", "update", "delete"]
        for method in expected:
            assert hasattr(SecretRepository, method)
