from uuid import UUID

from modules.ai.domain.entities import (
    Agent,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    ProviderCredential,
)
from modules.ai.domain.enums import (
    ContractStatus,
    ModelConfigStatus,
    PromptStatus,
    ReleaseStatus,
    ReleaseTestStatus,
)
from modules.ai.domain.repositories import (
    AgentContractRepository,
    AgentModelConfigRepository,
    AgentPromptRepository,
    AgentReleaseRepository,
    AgentReleaseTestRepository,
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.ai.service.dtos import (
    CreateAgentInput,
    CreateContractInput,
    CreateContractOutput,
    CreateModelConfigInput,
    CreateModelConfigOutput,
    CreatePromptInput,
    CreatePromptOutput,
    CreateProviderCredentialInput,
    CreateProviderCredentialOutput,
    CreateReleaseInput,
    CreateReleaseOutput,
    CreateReleaseTestInput,
    CreateReleaseTestOutput,
    GetAgentInput,
    ListAgentsInput,
    ListAgentsOutput,
    ListContractsOutput,
    ListModelConfigsOutput,
    ListPromptsOutput,
    ListProviderCredentialsInput,
    ListProviderCredentialsOutput,
    ListReleaseTestsOutput,
    ListReleasesOutput,
    PromoteReleaseInput,
    RollbackReleaseInput,
    UpdateAgentInput,
    UpdateAgentOutput,
    UpdateContractInput,
    UpdateContractOutput,
    UpdateProviderCredentialInput,
    UpdateProviderCredentialOutput,
)
from shared.domain.events import OutboxEventWriter
from shared.infra.config import Settings
from shared.infra.crypto import encrypt_secret


class CreateProviderCredentialUseCase:

    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
        encryption_key: str | None = None,
    ) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(
        self, input_dto: CreateProviderCredentialInput
    ) -> CreateProviderCredentialOutput:
        encrypted_secret = encrypt_secret(input_dto.secret, self._encryption_key)

        credential = ProviderCredential(
            project_id=input_dto.project_id,
            provider=input_dto.provider,
            name=input_dto.name,
            encrypted_secret=encrypted_secret,
            metadata=input_dto.metadata,
        )
        saved = await self._credential_repo.save(credential)

        await self._outbox.write(
            aggregate_type="provider_credential",
            aggregate_id=saved.id,
            event_type="provider_credential.created",
            payload={
                "project_id": str(saved.project_id),
                "provider": saved.provider.value,
                "name": saved.name,
            },
        )

        return CreateProviderCredentialOutput(
            id=saved.id,
            project_id=saved.project_id,
            provider=saved.provider,
            name=saved.name,
            status=saved.status,
            created_at=saved.created_at,
            metadata=saved.metadata,
        )


class UpdateProviderCredentialUseCase:

    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
        encryption_key: str | None = None,
    ) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(
        self, credential_id: UUID, input_dto: UpdateProviderCredentialInput
    ) -> UpdateProviderCredentialOutput:
        existing = await self._credential_repo.get_by_id(credential_id)
        if not existing:
            from modules.ai.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(credential_id)

        update_data = input_dto.model_dump(exclude_unset=True)
        if "secret" in update_data:
            update_data["encrypted_secret"] = encrypt_secret(input_dto.secret, self._encryption_key)
            del update_data["secret"]
        for field, value in update_data.items():
            setattr(existing, field, value)

        saved = await self._credential_repo.update(existing)

        await self._outbox.write(
            aggregate_type="provider_credential",
            aggregate_id=saved.id,
            event_type="provider_credential.updated",
            payload={
                "project_id": str(saved.project_id),
                "provider": saved.provider.value if hasattr(saved.provider, 'value') else saved.provider,
                "name": saved.name,
            },
        )

        return UpdateProviderCredentialOutput(
            id=saved.id,
            project_id=saved.project_id,
            provider=saved.provider,
            name=saved.name,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
            metadata=saved.metadata,
        )


class CreateAgentUseCase:

    def __init__(
        self,
        agent_repo: AgentRepository,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateAgentInput) -> Agent:
        if input_dto.provider_credential_id:
            cred = await self._credential_repo.get_by_id(
                input_dto.provider_credential_id
            )
            if not cred:
                from modules.ai.domain.errors import CredentialNotFoundError
                raise CredentialNotFoundError(input_dto.provider_credential_id)

        agent = Agent(
            project_id=input_dto.project_id,
            provider_credential_id=input_dto.provider_credential_id,
            fallback_credential_id=input_dto.fallback_credential_id,
            name=input_dto.name,
            description=input_dto.description,
            type=input_dto.type,
            system_prompt=input_dto.system_prompt,
            provider=input_dto.provider,
            model=input_dto.model,
            fallback_provider=input_dto.fallback_provider,
            fallback_model=input_dto.fallback_model,
            temperature=input_dto.temperature,
            max_output_tokens=input_dto.max_output_tokens,
            session_mode=input_dto.session_mode,
            settings=input_dto.settings,
        )
        saved = await self._agent_repo.save(agent)

        await self._outbox.write(
            aggregate_type="agent",
            aggregate_id=saved.id,
            event_type="agent.created",
            payload={
                "project_id": str(saved.project_id),
                "name": saved.name,
                "provider": saved.provider.value,
                "model": saved.model,
            },
        )

        return saved


class UpdateAgentUseCase:

    def __init__(
        self,
        agent_repo: AgentRepository,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._outbox = outbox

    async def execute(self, agent_id: UUID, input_dto: UpdateAgentInput) -> UpdateAgentOutput:
        existing = await self._agent_repo.get_by_id(agent_id)
        if not existing:
            from modules.ai.domain.errors import AgentNotFoundError
            raise AgentNotFoundError(agent_id)

        if input_dto.provider_credential_id is not None:
            cred = await self._credential_repo.get_by_id(input_dto.provider_credential_id)
            if not cred:
                from modules.ai.domain.errors import CredentialNotFoundError
                raise CredentialNotFoundError(input_dto.provider_credential_id)

        update_data = input_dto.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)

        saved = await self._agent_repo.update(existing)

        await self._outbox.write(
            aggregate_type="agent",
            aggregate_id=saved.id,
            event_type="agent.updated",
            payload={
                "project_id": str(saved.project_id),
                "name": saved.name,
                "provider": saved.provider.value if hasattr(saved.provider, 'value') else saved.provider,
                "model": saved.model,
            },
        )

        return UpdateAgentOutput(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            type=saved.type,
            provider=saved.provider,
            model=saved.model,
            provider_credential_id=saved.provider_credential_id,
            fallback_credential_id=saved.fallback_credential_id,
            fallback_provider=saved.fallback_provider,
            fallback_model=saved.fallback_model,
            temperature=saved.temperature,
            max_output_tokens=saved.max_output_tokens,
            session_mode=saved.session_mode,
            system_prompt=saved.system_prompt,
            description=saved.description,
            status=saved.status,
            settings=saved.settings,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListProviderCredentialsUseCase:

    def __init__(self, credential_repo: ProviderCredentialRepository) -> None:
        self._credential_repo = credential_repo

    async def execute(self, input_dto: ListProviderCredentialsInput) -> list[ListProviderCredentialsOutput]:
        if not input_dto.project_id:
            return []
        credentials = await self._credential_repo.list_by_project(input_dto.project_id)
        return [ListProviderCredentialsOutput(
            id=c.id,
            project_id=c.project_id,
            provider=c.provider,
            name=c.name,
            status=c.status,
            created_at=c.created_at,
            metadata=c.metadata,
        ) for c in credentials]


class ListAgentsUseCase:

    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, input_dto: ListAgentsInput) -> list[ListAgentsOutput]:
        if not input_dto.project_id:
            return []
        agents = await self._agent_repo.list_by_project(input_dto.project_id)
        return [ListAgentsOutput(
            id=a.id,
            project_id=a.project_id,
            name=a.name,
            provider=a.provider,
            model=a.model,
            status=a.status,
            created_at=a.created_at,
        ) for a in agents]


class GetAgentByIdUseCase:

    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, input_dto: GetAgentInput) -> Agent:
        from modules.ai.domain.errors import AgentNotFoundError
        agent = await self._agent_repo.get_by_id(input_dto.agent_id)
        if not agent:
            raise AgentNotFoundError(input_dto.agent_id)
        return agent


# ── Agent Prompt ────────────────────────────────────────────────

class CreatePromptUseCase:

    def __init__(self, prompt_repo: AgentPromptRepository) -> None:
        self._prompt_repo = prompt_repo

    async def execute(self, input_dto: CreatePromptInput) -> CreatePromptOutput:
        prompt = AgentPrompt(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=input_dto.version,
            name=input_dto.name,
            content=input_dto.content,
            content_hash=input_dto.content_hash,
            status=PromptStatus.draft,
            created_by=input_dto.created_by,
        )
        saved = await self._prompt_repo.save(prompt)
        return CreatePromptOutput(
            id=saved.id,
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            version=saved.version,
            name=saved.name,
            content=saved.content,
            status=saved.status,
            created_by=saved.created_by,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListPromptsUseCase:

    def __init__(self, prompt_repo: AgentPromptRepository) -> None:
        self._prompt_repo = prompt_repo

    async def execute(self, agent_id: UUID) -> list[ListPromptsOutput]:
        prompts = await self._prompt_repo.list_by_agent(agent_id)
        return [
            ListPromptsOutput(
                id=p.id,
                version=p.version,
                name=p.name,
                content=p.content,
                status=p.status,
                content_hash=p.content_hash,
                created_by=p.created_by,
                created_at=p.created_at,
            )
            for p in prompts
        ]


class GetPromptUseCase:

    def __init__(self, prompt_repo: AgentPromptRepository) -> None:
        self._prompt_repo = prompt_repo

    async def execute(self, prompt_id: UUID) -> AgentPrompt:
        from modules.ai.domain.errors import PromptNotFoundError
        prompt = await self._prompt_repo.get_by_id(prompt_id)
        if not prompt:
            raise PromptNotFoundError
        return prompt


# ── Agent Contract ──────────────────────────────────────────────

class CreateContractUseCase:

    def __init__(self, contract_repo: AgentContractRepository) -> None:
        self._contract_repo = contract_repo

    async def execute(self, input_dto: CreateContractInput) -> CreateContractOutput:
        contract = AgentContract(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=input_dto.version,
            name=input_dto.name,
            input_schema=input_dto.input_schema,
            output_schema=input_dto.output_schema,
            validation_mode=input_dto.validation_mode,
            repair_attempts=input_dto.repair_attempts,
            additional_instructions=input_dto.additional_instructions,
            schema_hash=input_dto.schema_hash,
            status=ContractStatus.draft,
        )
        saved = await self._contract_repo.save(contract)
        return CreateContractOutput(
            id=saved.id,
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            version=saved.version,
            name=saved.name,
            input_schema=saved.input_schema,
            output_schema=saved.output_schema,
            validation_mode=saved.validation_mode,
            repair_attempts=saved.repair_attempts,
            additional_instructions=saved.additional_instructions,
            schema_hash=saved.schema_hash,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class UpdateContractUseCase:

    def __init__(self, contract_repo: AgentContractRepository) -> None:
        self._contract_repo = contract_repo

    async def execute(
        self, contract_id: UUID, input_dto: UpdateContractInput
    ) -> UpdateContractOutput:
        from modules.ai.domain.errors import ContractNotFoundError
        existing = await self._contract_repo.get_by_id(contract_id)
        if not existing:
            raise ContractNotFoundError

        update_data = input_dto.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)

        saved = await self._contract_repo.save(existing)
        return UpdateContractOutput(
            id=saved.id,
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            version=saved.version,
            name=saved.name,
            input_schema=saved.input_schema,
            output_schema=saved.output_schema,
            validation_mode=saved.validation_mode,
            repair_attempts=saved.repair_attempts,
            additional_instructions=saved.additional_instructions,
            schema_hash=saved.schema_hash,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListContractsUseCase:

    def __init__(self, contract_repo: AgentContractRepository) -> None:
        self._contract_repo = contract_repo

    async def execute(self, agent_id: UUID) -> list[ListContractsOutput]:
        contracts = await self._contract_repo.list_by_agent(agent_id)
        return [
            ListContractsOutput(
                id=c.id,
                version=c.version,
                name=c.name,
                validation_mode=c.validation_mode,
                status=c.status,
                created_at=c.created_at,
            )
            for c in contracts
        ]


class GetContractUseCase:

    def __init__(self, contract_repo: AgentContractRepository) -> None:
        self._contract_repo = contract_repo

    async def execute(self, contract_id: UUID) -> AgentContract:
        from modules.ai.domain.errors import ContractNotFoundError
        contract = await self._contract_repo.get_by_id(contract_id)
        if not contract:
            raise ContractNotFoundError
        return contract


# ── Agent Model Config ──────────────────────────────────────────

class CreateModelConfigUseCase:

    def __init__(self, config_repo: AgentModelConfigRepository) -> None:
        self._config_repo = config_repo

    async def execute(self, input_dto: CreateModelConfigInput) -> CreateModelConfigOutput:
        config = AgentModelConfig(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=input_dto.version,
            provider=input_dto.provider,
            provider_credential_id=input_dto.provider_credential_id,
            model=input_dto.model,
            base_url=input_dto.base_url,
            temperature=input_dto.temperature,
            max_output_tokens=input_dto.max_output_tokens,
            session_mode=input_dto.session_mode,
            settings=input_dto.settings,
            status=ModelConfigStatus.draft,
        )
        saved = await self._config_repo.save(config)
        return CreateModelConfigOutput(
            id=saved.id,
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            version=saved.version,
            provider=saved.provider,
            provider_credential_id=saved.provider_credential_id,
            model=saved.model,
            base_url=saved.base_url,
            temperature=saved.temperature,
            max_output_tokens=saved.max_output_tokens,
            session_mode=saved.session_mode,
            settings=saved.settings,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListModelConfigsUseCase:

    def __init__(self, config_repo: AgentModelConfigRepository) -> None:
        self._config_repo = config_repo

    async def execute(self, agent_id: UUID) -> list[ListModelConfigsOutput]:
        configs = await self._config_repo.list_by_agent(agent_id)
        return [
            ListModelConfigsOutput(
                id=c.id,
                version=c.version,
                provider=c.provider,
                model=c.model,
                status=c.status,
                created_at=c.created_at,
            )
            for c in configs
        ]


class GetModelConfigUseCase:

    def __init__(self, config_repo: AgentModelConfigRepository) -> None:
        self._config_repo = config_repo

    async def execute(self, config_id: UUID) -> AgentModelConfig:
        from modules.ai.domain.errors import ModelConfigNotFoundError
        config = await self._config_repo.get_by_id(config_id)
        if not config:
            raise ModelConfigNotFoundError
        return config


# ── Agent Release ───────────────────────────────────────────────

class CreateReleaseUseCase:

    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, input_dto: CreateReleaseInput) -> CreateReleaseOutput:
        release = AgentRelease(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=input_dto.version,
            status=ReleaseStatus.draft,
            prompt_version_id=input_dto.prompt_version_id,
            contract_version_id=input_dto.contract_version_id,
            knowledge_version_id=input_dto.knowledge_version_id,
            model_config_version_id=input_dto.model_config_version_id,
            # Snapshot fields — complete agent config
            name=input_dto.name,
            description=input_dto.description,
            system_prompt=input_dto.system_prompt,
            response_format=input_dto.response_format,
            output_schema=input_dto.output_schema,
            provider=input_dto.provider,
            model=input_dto.model,
            provider_credential_id=input_dto.provider_credential_id,
            fallback_provider=input_dto.fallback_provider,
            fallback_model=input_dto.fallback_model,
            fallback_credential_id=input_dto.fallback_credential_id,
            base_url=input_dto.base_url,
            temperature=input_dto.temperature,
            max_output_tokens=input_dto.max_output_tokens,
            session_mode=input_dto.session_mode,
            agent_status=input_dto.agent_status,
            collection_ids=input_dto.collection_ids,
            runtime_config=input_dto.runtime_config,
            # Meta
            release_notes=input_dto.release_notes,
            risk_score=input_dto.risk_score,
            created_by=input_dto.created_by,
        )
        saved = await self._release_repo.save(release)
        return _release_to_output(saved)


def _release_to_output(saved: AgentRelease) -> CreateReleaseOutput:
    return CreateReleaseOutput(
        id=saved.id,
        project_id=saved.project_id,
        agent_id=saved.agent_id,
        version=saved.version,
        status=saved.status,
        prompt_version_id=saved.prompt_version_id,
        contract_version_id=saved.contract_version_id,
        knowledge_version_id=saved.knowledge_version_id,
        model_config_version_id=saved.model_config_version_id,
        name=saved.name,
        description=saved.description,
        system_prompt=saved.system_prompt,
        response_format=saved.response_format,
        output_schema=saved.output_schema,
        provider=saved.provider,
        model=saved.model,
        provider_credential_id=saved.provider_credential_id,
        fallback_provider=saved.fallback_provider,
        fallback_model=saved.fallback_model,
        fallback_credential_id=saved.fallback_credential_id,
        base_url=saved.base_url,
        temperature=saved.temperature,
        max_output_tokens=saved.max_output_tokens,
        session_mode=saved.session_mode,
        agent_status=saved.agent_status,
        collection_ids=saved.collection_ids,
        runtime_config=saved.runtime_config,
        release_notes=saved.release_notes,
        risk_score=saved.risk_score,
        created_by=saved.created_by,
        promoted_by=saved.promoted_by,
        promoted_at=saved.promoted_at,
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


class ListReleasesUseCase:

    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, agent_id: UUID) -> list[ListReleasesOutput]:
        releases = await self._release_repo.list_by_agent(agent_id)
        return [
            ListReleasesOutput(
                id=r.id,
                version=r.version,
                status=r.status,
                name=r.name,
                provider=r.provider,
                model=r.model,
                system_prompt=r.system_prompt,
                output_schema=r.output_schema,
                risk_score=r.risk_score,
                release_notes=r.release_notes,
                created_by=r.created_by,
                created_at=r.created_at,
                promoted_at=r.promoted_at,
            )
            for r in releases
        ]


class GetReleaseUseCase:

    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, release_id: UUID) -> AgentRelease:
        from modules.ai.domain.errors import ReleaseNotFoundError
        release = await self._release_repo.get_by_id(release_id)
        if not release:
            raise ReleaseNotFoundError
        return release


class PromoteReleaseUseCase:

    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(
        self, agent_id: UUID, release_id: UUID, input_dto: PromoteReleaseInput
    ) -> CreateReleaseOutput:
        from datetime import datetime, timezone
        from modules.ai.domain.errors import ReleaseNotFoundError

        release = await self._release_repo.get_by_id(release_id)
        if not release or release.agent_id != agent_id:
            raise ReleaseNotFoundError

        current_production = await self._release_repo.list_by_status(
            release.agent_id, ReleaseStatus.production
        )
        for prod_release in current_production:
            prod_release.status = ReleaseStatus.archived
            await self._release_repo.save(prod_release)

        release.status = ReleaseStatus.production
        release.promoted_by = input_dto.user_id
        release.promoted_at = datetime.now(timezone.utc)
        saved = await self._release_repo.save(release)

        return _release_to_output(saved)


class RollbackReleaseUseCase:

    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(
        self, agent_id: UUID, release_id: UUID, input_dto: RollbackReleaseInput
    ) -> CreateReleaseOutput:
        from datetime import datetime, timezone
        from modules.ai.domain.errors import ReleaseNotFoundError

        release = await self._release_repo.get_by_id(release_id)
        if not release or release.agent_id != agent_id:
            raise ReleaseNotFoundError

        target_is_production = release.status == ReleaseStatus.production

        current_production = await self._release_repo.list_by_status(
            release.agent_id, ReleaseStatus.production
        )

        # Archive all current production releases
        for prod_release in current_production:
            prod_release.status = ReleaseStatus.rolled_back
            await self._release_repo.save(prod_release)

        if target_is_production:
            # Rolling back the current production → restore the last promoted release
            previous = await self._release_repo.get_last_promoted(
                release.agent_id, exclude_id=release.id
            )
            if previous:
                previous.status = ReleaseStatus.production
                previous.promoted_by = input_dto.user_id
                previous.promoted_at = datetime.now(timezone.utc)
                saved = await self._release_repo.save(previous)
                return _release_to_output(saved)
            return _release_to_output(release)

        # Target is not production → make it the new production
        release.status = ReleaseStatus.production
        release.promoted_by = input_dto.user_id
        release.promoted_at = datetime.now(timezone.utc)
        saved = await self._release_repo.save(release)

        return _release_to_output(saved)


# ── Agent Release Test ──────────────────────────────────────────

class CreateReleaseTestUseCase:

    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, input_dto: CreateReleaseTestInput) -> CreateReleaseTestOutput:
        test = AgentReleaseTest(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            release_id=input_dto.release_id,
            contract_version_id=input_dto.contract_version_id,
            input_payload=input_dto.input_payload,
            expected_output=input_dto.expected_output,
            status=ReleaseTestStatus.pending,
        )
        saved = await self._test_repo.save(test)
        return CreateReleaseTestOutput(
            id=saved.id,
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            release_id=saved.release_id,
            contract_version_id=saved.contract_version_id,
            input_payload=saved.input_payload,
            expected_output=saved.expected_output,
            actual_output=saved.actual_output,
            status=saved.status,
            validation_errors=saved.validation_errors,
            latency_ms=saved.latency_ms,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListReleaseTestsUseCase:

    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, release_id: UUID) -> list[ListReleaseTestsOutput]:
        tests = await self._test_repo.list_by_release(release_id)
        return [
            ListReleaseTestsOutput(
                id=t.id,
                release_id=t.release_id,
                contract_version_id=t.contract_version_id,
                status=t.status,
                validation_errors=t.validation_errors,
                latency_ms=t.latency_ms,
                created_at=t.created_at,
            )
            for t in tests
        ]


class GetReleaseTestUseCase:

    def __init__(self, test_repo: AgentReleaseTestRepository) -> None:
        self._test_repo = test_repo

    async def execute(self, test_id: UUID) -> AgentReleaseTest:
        from modules.ai.domain.errors import ReleaseTestNotFoundError
        test = await self._test_repo.get_by_id(test_id)
        if not test:
            raise ReleaseTestNotFoundError
        return test


# ── Delete Release ─────────────────────────────────────────────

class DeleteReleaseUseCase:

    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, release_id: UUID) -> None:
        from modules.ai.domain.errors import ReleaseNotFoundError

        release = await self._release_repo.get_by_id(release_id)
        if not release:
            raise ReleaseNotFoundError

        if release.status == ReleaseStatus.production:
            from shared.domain.errors import ValidationError
            raise ValidationError("Cannot delete a production release. Rollback first.")

        await self._release_repo.delete(release_id)

