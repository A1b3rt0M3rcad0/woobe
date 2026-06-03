import uuid6
from datetime import datetime
from uuid import UUID

from modules.ai.domain.entities import Agent, ProviderCredential
from modules.ai.domain.enums import (
    AgentStatus,
    AgentType,
    CredentialStatus,
    Provider,
    SessionMode,
)


class TestProviderCredential:
    def test_default_creation(self):
        c = ProviderCredential()
        assert isinstance(c.id, UUID)
        assert isinstance(c.project_id, UUID)
        assert c.provider == Provider.openai
        assert c.name == ""
        assert c.encrypted_secret == ""
        assert c.status == CredentialStatus.active
        assert c.last_validated_at is None
        assert c.created_at is None
        assert c.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        c = ProviderCredential(
            id=uuid6.uuid7(),
            project_id=uuid6.uuid7(),
            provider=Provider.anthropic,
            name="Anthropic Key",
            encrypted_secret="enc:abc",
            status=CredentialStatus.expired,
            last_validated_at=now,
            created_at=now,
            updated_at=now,
        )
        assert isinstance(c.provider, Provider)
        assert isinstance(c.name, str)
        assert isinstance(c.encrypted_secret, str)
        assert isinstance(c.status, CredentialStatus)

    def test_uuid_generation(self):
        c1 = ProviderCredential()
        c2 = ProviderCredential()
        assert c1.id != c2.id


class TestAgent:
    def test_default_creation(self):
        a = Agent()
        assert isinstance(a.id, UUID)
        assert isinstance(a.project_id, UUID)
        assert a.provider_credential_id is None
        assert a.fallback_credential_id is None
        assert a.name == ""
        assert a.description == ""
        assert a.type == AgentType.chat
        assert a.system_prompt == ""
        assert a.provider == Provider.openai
        assert a.model == ""
        assert a.fallback_provider is None
        assert a.fallback_model is None
        assert a.temperature is None
        assert a.max_output_tokens is None
        assert a.session_mode == SessionMode.stateless
        assert a.status == AgentStatus.active
        assert a.settings == {}
        assert a.created_at is None
        assert a.updated_at is None

    def test_field_types(self):
        now = datetime.now()
        a = Agent(
            id=uuid6.uuid7(),
            project_id=uuid6.uuid7(),
            provider_credential_id=uuid6.uuid7(),
            fallback_credential_id=uuid6.uuid7(),
            name="Helper",
            description="A helpful agent",
            type=AgentType.assistant,
            system_prompt="Be helpful",
            provider=Provider.anthropic,
            model="claude-3",
            fallback_provider=Provider.openai,
            fallback_model="gpt-4",
            temperature=0.7,
            max_output_tokens=4096,
            session_mode=SessionMode.stateful,
            status=AgentStatus.inactive,
            settings={"key": "val"},
            created_at=now,
            updated_at=now,
        )
        assert isinstance(a.type, AgentType)
        assert isinstance(a.provider, Provider)
        assert isinstance(a.session_mode, SessionMode)
        assert isinstance(a.status, AgentStatus)
        assert isinstance(a.settings, dict)

    def test_uuid_generation(self):
        a1 = Agent()
        a2 = Agent()
        assert a1.id != a2.id
