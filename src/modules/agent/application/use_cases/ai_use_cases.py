from uuid import UUID
from datetime import datetime, timezone

from modules.agent.domain.entities import (
    Agent,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    ProviderCredential,
)
from modules.agent.domain.enums import (
    ContractStatus,
    ModelConfigStatus,
    PromptStatus,
    ReleaseStatus,
    ReleaseTestStatus,
)
from modules.agent.domain.repositories import (
    AgentContractRepository,
    AgentModelConfigRepository,
    AgentPromptRepository,
    AgentReleaseRepository,
    AgentReleaseTestRepository,
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.agent.application.dtos.ai_dtos import *
from modules.agent.domain.events import (
    AgentProviderCredentialCreatedV1,
    AgentProviderCredentialUpdatedV1,
)
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.infra.config import Settings
from shared.infra.crypto import encrypt_secret


class CreateProviderCredentialUseCase:
    def __init__(self, credential_repo: ProviderCredentialRepository, outbox: OutboxEventWriter, encryption_key: str | None = None) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(self, input_dto: CreateProviderCredentialInput) -> CreateProviderCredentialOutput:
        saved = await self._credential_repo.save(ProviderCredential(project_id=input_dto.project_id, provider=input_dto.provider, name=input_dto.name, encrypted_secret=encrypt_secret(input_dto.secret, self._encryption_key), metadata=input_dto.metadata))
        await self._outbox.write(AgentProviderCredentialCreatedV1.create(credential_id=saved.id, project_id=saved.project_id, provider=saved.provider.value if hasattr(saved.provider, "value") else saved.provider, name=saved.name))
        return CreateProviderCredentialOutput(id=saved.id, project_id=saved.project_id, provider=saved.provider, name=saved.name, status=saved.status, created_at=saved.created_at, metadata=saved.metadata)


class UpdateProviderCredentialUseCase:
    def __init__(self, credential_repo: ProviderCredentialRepository, outbox: OutboxEventWriter, encryption_key: str | None = None) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(self, credential_id: UUID, input_dto: UpdateProviderCredentialInput) -> UpdateProviderCredentialOutput:
        existing = await self._credential_repo.get_by_id(credential_id)
        if not existing:
            from modules.agent.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(credential_id)
        data = input_dto.model_dump(exclude_unset=True)
        if "secret" in data:
            data["encrypted_secret"] = encrypt_secret(input_dto.secret, self._encryption_key)
            del data["secret"]
        for field, value in data.items():
            setattr(existing, field, value)
        saved = await self._credential_repo.update(existing)
        await self._outbox.write(AgentProviderCredentialUpdatedV1.create(credential_id=saved.id, project_id=saved.project_id, provider=saved.provider.value if hasattr(saved.provider, "value") else saved.provider, name=saved.name))
        return UpdateProviderCredentialOutput(id=saved.id, project_id=saved.project_id, provider=saved.provider, name=saved.name, status=saved.status, created_at=saved.created_at, updated_at=saved.updated_at, metadata=saved.metadata)


def _release_to_output(saved: AgentRelease) -> CreateReleaseOutput:
    return CreateReleaseOutput(id=saved.id, project_id=saved.project_id, agent_id=saved.agent_id, version=saved.version, status=saved.status, prompt_version_id=saved.prompt_version_id, contract_version_id=saved.contract_version_id, knowledge_version_id=saved.knowledge_version_id, model_config_version_id=saved.model_config_version_id, name=saved.name, description=saved.description, system_prompt=saved.system_prompt, response_format=saved.response_format, output_schema=saved.output_schema, provider=saved.provider, model=saved.model, provider_credential_id=saved.provider_credential_id, fallback_provider=saved.fallback_provider, fallback_model=saved.fallback_model, fallback_credential_id=saved.fallback_credential_id, base_url=saved.base_url, temperature=saved.temperature, max_output_tokens=saved.max_output_tokens, session_mode=saved.session_mode, agent_status=saved.agent_status, collection_ids=saved.collection_ids, runtime_config=saved.runtime_config, release_notes=saved.release_notes, risk_score=saved.risk_score, created_by=saved.created_by, promoted_by=saved.promoted_by, promoted_at=saved.promoted_at, created_at=saved.created_at, updated_at=saved.updated_at)


class ListReleasesUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, agent_id: UUID) -> list[ListReleasesOutput]:
        return [ListReleasesOutput(**_release_to_output(item).model_dump()) for item in await self._release_repo.list_by_agent(agent_id)]


class GetReleaseUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, release_id: UUID) -> AgentRelease:
        from modules.agent.domain.errors import ReleaseNotFoundError
        item = await self._release_repo.get_by_id(release_id)
        if not item:
            raise ReleaseNotFoundError
        return item


class DeleteReleaseUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, release_id: UUID) -> None:
        await self._release_repo.delete(release_id)


class CreateReleaseTestUseCase:
    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, input_dto: CreateReleaseTestInput) -> CreateReleaseTestOutput:
        saved = await self._test_repo.save(AgentReleaseTest(project_id=input_dto.project_id, agent_id=input_dto.agent_id, release_id=input_dto.release_id, contract_version_id=input_dto.contract_version_id, input_payload=input_dto.input_payload, expected_output=input_dto.expected_output, status=ReleaseTestStatus.pending))
        return CreateReleaseTestOutput(id=saved.id, project_id=saved.project_id, agent_id=saved.agent_id, release_id=saved.release_id, contract_version_id=saved.contract_version_id, input_payload=saved.input_payload, expected_output=saved.expected_output, actual_output=saved.actual_output, status=saved.status, validation_errors=saved.validation_errors, latency_ms=saved.latency_ms, created_at=saved.created_at, updated_at=saved.updated_at)


class ListReleaseTestsUseCase:
    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, release_id: UUID) -> list[ListReleaseTestsOutput]:
        return [ListReleaseTestsOutput(id=item.id, release_id=item.release_id, contract_version_id=item.contract_version_id, status=item.status, validation_errors=item.validation_errors, latency_ms=item.latency_ms, created_at=item.created_at) for item in await self._test_repo.list_by_release(release_id)]


class GetReleaseTestUseCase:
    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, test_id: UUID) -> AgentReleaseTest:
        from modules.agent.domain.errors import ReleaseTestNotFoundError
        item = await self._test_repo.get_by_id(test_id)
        if not item:
            raise ReleaseTestNotFoundError
        return item


from modules.agent.application.use_cases.release_lifecycle_use_cases import AutoCreateReleaseUseCase as CreateReleaseUseCase
from modules.agent.application.use_cases.release_promote_compat import PromoteReleaseUseCase
from modules.agent.application.use_cases.release_promote_compat import PromoteReleaseUseCase as RollbackReleaseUseCase
from modules.agent.application.use_cases.ai_agent_cases import CreateAgentUseCase, UpdateAgentUseCase, ListAgentsUseCase, GetAgentByIdUseCase
from modules.agent.application.use_cases.ai_prompt_cases import CreatePromptUseCase, ListPromptsUseCase, GetPromptUseCase


class _UnavailableUseCase:
    def __init__(self, *args, **kwargs):
        pass
    async def execute(self, *args, **kwargs):
        raise NotImplementedError


CreateContractUseCase = _UnavailableUseCase
UpdateContractUseCase = _UnavailableUseCase
ListContractsUseCase = _UnavailableUseCase
GetContractUseCase = _UnavailableUseCase
CreateModelConfigUseCase = _UnavailableUseCase
ListModelConfigsUseCase = _UnavailableUseCase
GetModelConfigUseCase = _UnavailableUseCase
