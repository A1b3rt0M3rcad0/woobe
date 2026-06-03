import uuid
from datetime import datetime, timezone

from modules.tools.domain.entities import Secret, Tool
from modules.tools.domain.enums import RiskLevel, SecretType, ToolStatus, ToolType


class TestTool:
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


class TestSecret:
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
