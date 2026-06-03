import uuid
from datetime import datetime, timezone

from modules.runtime.domain.entities import Message, Session
from modules.runtime.domain.enums import MessageRole, SessionMode, SessionStatus


class TestSession:
    def test_defaults(self):
        s = Session()
        assert isinstance(s.id, uuid.UUID)
        assert s.project_id is None
        assert s.agent_id is None
        assert s.external_session_id is None
        assert s.tenant_id is None
        assert s.user_id is None
        assert s.status == SessionStatus.ACTIVE
        assert s.mode == SessionMode.CHAT
        assert s.data is None
        assert s.last_message_at is None
        assert s.created_at is None
        assert s.updated_at is None

    def test_custom_values(self):
        now = datetime.now(timezone.utc)
        sid = uuid.uuid4()
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        s = Session(
            id=sid,
            project_id=pid,
            agent_id=aid,
            external_session_id="ext-456",
            tenant_id="tenant1",
            user_id="user1",
            status=SessionStatus.CLOSED,
            mode=SessionMode.WORKFLOW,
            data={"env": "prod"},
            last_message_at=now,
            created_at=now,
            updated_at=now,
        )
        assert s.id == sid
        assert s.project_id == pid
        assert s.agent_id == aid
        assert s.external_session_id == "ext-456"
        assert s.tenant_id == "tenant1"
        assert s.user_id == "user1"
        assert s.status == SessionStatus.CLOSED
        assert s.mode == SessionMode.WORKFLOW
        assert s.data == {"env": "prod"}
        assert s.last_message_at == now

    def test_uuid_generation(self):
        s1 = Session()
        s2 = Session()
        assert s1.id != s2.id


class TestMessage:
    def test_defaults(self):
        m = Message()
        assert isinstance(m.id, uuid.UUID)
        assert m.project_id is None
        assert m.agent_id is None
        assert m.session_id is None
        assert m.role == MessageRole.USER
        assert m.content == ""
        assert m.input_tokens is None
        assert m.output_tokens is None
        assert m.cost_usd is None
        assert m.data is None
        assert m.created_at is None
        assert m.updated_at is None

    def test_custom_values(self):
        now = datetime.now(timezone.utc)
        mid = uuid.uuid4()
        pid = uuid.uuid4()
        aid = uuid.uuid4()
        sid = uuid.uuid4()
        m = Message(
            id=mid,
            project_id=pid,
            agent_id=aid,
            session_id=sid,
            role=MessageRole.ASSISTANT,
            content="Hello!",
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.0015,
            data={"model": "gpt-4"},
            created_at=now,
            updated_at=now,
        )
        assert m.id == mid
        assert m.project_id == pid
        assert m.agent_id == aid
        assert m.session_id == sid
        assert m.role == MessageRole.ASSISTANT
        assert m.content == "Hello!"
        assert m.input_tokens == 10
        assert m.output_tokens == 20
        assert m.cost_usd == 0.0015
        assert m.data == {"model": "gpt-4"}
        assert m.created_at == now
        assert m.updated_at == now

    def test_uuid_generation(self):
        m1 = Message()
        m2 = Message()
        assert m1.id != m2.id
