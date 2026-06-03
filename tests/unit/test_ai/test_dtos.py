from uuid import UUID

from modules.ai.domain.enums import AgentStatus, AgentType, CredentialStatus, Provider, SessionMode
from modules.ai.service.dtos import (
    CreateAgentInput,
    CreateAgentOutput,
    CreateProviderCredentialInput,
    CreateProviderCredentialOutput,
)


class TestCreateProviderCredentialInput:
    def test_creation(self):
        pid = UUID("00000000-0000-0000-0000-000000000001")
        dto = CreateProviderCredentialInput(
            project_id=pid,
            provider=Provider.anthropic,
            name="Anthropic Key",
            secret="sk-ant-xxx",
        )
        assert dto.project_id == pid
        assert dto.provider == Provider.anthropic
        assert dto.name == "Anthropic Key"
        assert dto.secret == "sk-ant-xxx"

    def test_field_presence(self):
        fields = CreateProviderCredentialInput.model_fields
        assert "project_id" in fields
        assert "provider" in fields
        assert "name" in fields
        assert "secret" in fields


class TestCreateProviderCredentialOutput:
    def test_creation(self):
        dto = CreateProviderCredentialOutput(
            id=UUID("00000000-0000-0000-0000-000000000002"),
            project_id=UUID("00000000-0000-0000-0000-000000000003"),
            provider=Provider.openai,
            name="OpenAI Key",
            status=CredentialStatus.active,
            created_at="2025-01-01T00:00:00Z",
        )
        assert dto.provider == Provider.openai
        assert dto.status == CredentialStatus.active

    def test_field_presence(self):
        fields = CreateProviderCredentialOutput.model_fields
        assert "id" in fields
        assert "project_id" in fields
        assert "provider" in fields
        assert "name" in fields
        assert "status" in fields
        assert "created_at" in fields


class TestCreateAgentInput:
    def test_creation(self):
        pid = UUID("00000000-0000-0000-0000-000000000004")
        dto = CreateAgentInput(
            project_id=pid,
            name="Helper",
            description="A helpful agent",
            model="gpt-4",
            provider=Provider.openai,
            type=AgentType.chat,
            temperature=0.5,
            max_output_tokens=2048,
        )
        assert dto.project_id == pid
        assert dto.name == "Helper"
        assert dto.model == "gpt-4"
        assert dto.provider == Provider.openai
        assert dto.type == AgentType.chat
        assert dto.temperature == 0.5
        assert dto.max_output_tokens == 2048

    def test_defaults(self):
        pid = UUID("00000000-0000-0000-0000-000000000004")
        dto = CreateAgentInput(project_id=pid, name="Helper", model="gpt-4")
        assert dto.description == ""
        assert dto.type == AgentType.chat
        assert dto.provider == Provider.openai
        assert dto.session_mode == SessionMode.stateless
        assert dto.settings == {}
        assert dto.provider_credential_id is None
        assert dto.fallback_credential_id is None
        assert dto.temperature is None
        assert dto.max_output_tokens is None

    def test_field_presence(self):
        fields = CreateAgentInput.model_fields
        assert "project_id" in fields
        assert "provider_credential_id" in fields
        assert "fallback_credential_id" in fields
        assert "name" in fields
        assert "description" in fields
        assert "type" in fields
        assert "system_prompt" in fields
        assert "provider" in fields
        assert "model" in fields
        assert "fallback_provider" in fields
        assert "fallback_model" in fields
        assert "temperature" in fields
        assert "max_output_tokens" in fields
        assert "session_mode" in fields
        assert "settings" in fields


class TestCreateAgentOutput:
    def test_creation(self):
        dto = CreateAgentOutput(
            id=UUID("00000000-0000-0000-0000-000000000005"),
            project_id=UUID("00000000-0000-0000-0000-000000000006"),
            name="Helper",
            type=AgentType.chat,
            provider=Provider.openai,
            model="gpt-4",
            status=AgentStatus.active,
            created_at="2025-01-01T00:00:00Z",
        )
        assert dto.type == AgentType.chat
        assert dto.provider == Provider.openai
        assert dto.model == "gpt-4"
        assert dto.status == AgentStatus.active

    def test_field_presence(self):
        fields = CreateAgentOutput.model_fields
        assert "id" in fields
        assert "project_id" in fields
        assert "name" in fields
        assert "type" in fields
        assert "provider" in fields
        assert "model" in fields
        assert "status" in fields
        assert "created_at" in fields
