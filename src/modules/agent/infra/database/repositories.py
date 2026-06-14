from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.agent.domain.entities import (
    Agent,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    ProviderCredential,
)
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.repositories import (
    AgentContractRepository as AgentContractRepositoryInterface,
    AgentModelConfigRepository as AgentModelConfigRepositoryInterface,
    AgentPromptRepository as AgentPromptRepositoryInterface,
    AgentReleaseRepository as AgentReleaseRepositoryInterface,
    AgentReleaseTestRepository as AgentReleaseTestRepositoryInterface,
    AgentRepository as AgentRepositoryInterface,
    ProviderCredentialRepository as ProviderCredentialRepositoryInterface,
)
from modules.agent.infra.database.mappers import (
    agent_contract_entity_to_model,
    agent_contract_model_to_entity,
    agent_entity_to_model,
    agent_model_config_entity_to_model,
    agent_model_config_model_to_entity,
    agent_model_to_entity,
    agent_prompt_entity_to_model,
    agent_prompt_model_to_entity,
    agent_release_entity_to_model,
    agent_release_model_to_entity,
    agent_release_test_entity_to_model,
    agent_release_test_model_to_entity,
    provider_credential_entity_to_model,
    provider_credential_model_to_entity,
)
from modules.agent.infra.database.models import (
    AgentContractModel,
    AgentModel,
    AgentModelConfigModel,
    AgentPromptModel,
    AgentReleaseModel,
    AgentReleaseTestModel,
    OutboxEventModel,
    ProviderCredentialModel,
)
from shared.domain.events import OutboxEventWriter
from shared.domain.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


class SQLAlchemyProviderCredentialRepository(
    BaseSQLAlchemyRepository[ProviderCredentialModel],
    ProviderCredentialRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, ProviderCredentialModel)

    async def save(self, credential: ProviderCredential) -> ProviderCredential:
        model = provider_credential_entity_to_model(credential)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return provider_credential_model_to_entity(model)

    async def get_by_id(self, credential_id: UUID) -> ProviderCredential | None:
        model = await self._get_model_by_id(credential_id)
        return provider_credential_model_to_entity(model) if model else None

    async def list_by_project(
        self, project_id: UUID
    ) -> list[ProviderCredential]:
        # TODO: Remove after pagination migration
        result = await self._session.execute(
            select(ProviderCredentialModel).where(
                ProviderCredentialModel.project_id == project_id
            )
        )
        return [
            provider_credential_model_to_entity(c)
            for c in result.scalars().all()
        ]

    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[ProviderCredential]:
        stmt = (
            select(ProviderCredentialModel)
            .where(ProviderCredentialModel.project_id == project_id)
            .order_by(ProviderCredentialModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[provider_credential_model_to_entity(c) for c in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, credential: ProviderCredential) -> ProviderCredential:
        model = await self._get_model_by_id(credential.id)
        if not model:
            from modules.agent.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(credential.id)
        model.provider = credential.provider.value if hasattr(credential.provider, 'value') else credential.provider
        model.name = credential.name
        model.encrypted_secret = credential.encrypted_secret
        model.status = credential.status.value if hasattr(credential.status, 'value') else credential.status
        model.last_validated_at = credential.last_validated_at
        model.meta = credential.metadata or None
        await self._flush()
        return provider_credential_model_to_entity(model)

    async def delete(self, credential_id: UUID) -> None:
        model = await self._get_model_by_id(credential_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyAgentRepository(
    BaseSQLAlchemyRepository[AgentModel], AgentRepositoryInterface
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, AgentModel)

    async def save(self, agent: Agent) -> Agent:
        model = agent_entity_to_model(agent)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return agent_model_to_entity(model)

    async def get_by_id(self, agent_id: UUID) -> Agent | None:
        model = await self._get_model_by_id(agent_id)
        return agent_model_to_entity(model) if model else None

    async def update(self, agent: Agent) -> Agent:
        model = await self._get_model_by_id(agent.id)
        if not model:
            from modules.agent.domain.errors import AgentNotFoundError
            raise AgentNotFoundError(agent.id)
        model.name = agent.name
        model.description = agent.description
        model.system_prompt = agent.system_prompt
        model.provider = agent.provider.value if hasattr(agent.provider, 'value') else agent.provider
        model.model = agent.model
        model.provider_credential_id = agent.provider_credential_id
        model.fallback_provider = agent.fallback_provider.value if (hasattr(agent.fallback_provider, 'value') and agent.fallback_provider) else agent.fallback_provider
        model.fallback_model = agent.fallback_model
        model.fallback_credential_id = agent.fallback_credential_id
        model.temperature = agent.temperature
        model.max_output_tokens = agent.max_output_tokens
        model.session_mode = agent.session_mode.value if hasattr(agent.session_mode, 'value') else agent.session_mode
        model.status = agent.status.value if hasattr(agent.status, 'value') else agent.status
        model.settings = agent.settings
        await self._flush()
        return agent_model_to_entity(model)

    async def list_by_project(self, project_id: UUID) -> list[Agent]:
        # TODO: Remove after pagination migration
        result = await self._session.execute(
            select(AgentModel).where(AgentModel.project_id == project_id)
        )
        return [agent_model_to_entity(a) for a in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Agent]:
        stmt = (
            select(AgentModel)
            .where(AgentModel.project_id == project_id)
            .order_by(AgentModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[agent_model_to_entity(a) for a in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, agent_id: UUID) -> None:
        model = await self._get_model_by_id(agent_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)


class SQLAlchemyAgentPromptRepository(
    BaseSQLAlchemyRepository[AgentPromptModel],
    AgentPromptRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, AgentPromptModel)

    async def save(self, prompt: AgentPrompt) -> AgentPrompt:
        model = agent_prompt_entity_to_model(prompt)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return agent_prompt_model_to_entity(model)

    async def get_by_id(self, prompt_id: UUID) -> AgentPrompt | None:
        model = await self._get_model_by_id(prompt_id)
        return agent_prompt_model_to_entity(model) if model else None

    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentPrompt | None:
        result = await self._session.execute(
            select(AgentPromptModel).where(
                AgentPromptModel.agent_id == agent_id,
                AgentPromptModel.version == version,
            )
        )
        model = result.scalar_one_or_none()
        return agent_prompt_model_to_entity(model) if model else None

    async def list_by_agent(self, agent_id: UUID) -> list[AgentPrompt]:
        result = await self._session.execute(
            select(AgentPromptModel)
            .where(AgentPromptModel.agent_id == agent_id)
            .order_by(AgentPromptModel.created_at.desc())
        )
        return [agent_prompt_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentPrompt]:
        stmt = (
            select(AgentPromptModel)
            .where(AgentPromptModel.agent_id == agent_id)
            .order_by(AgentPromptModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[agent_prompt_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )


class SQLAlchemyAgentContractRepository(
    BaseSQLAlchemyRepository[AgentContractModel],
    AgentContractRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, AgentContractModel)

    async def save(self, contract: AgentContract) -> AgentContract:
        model = agent_contract_entity_to_model(contract)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return agent_contract_model_to_entity(model)

    async def get_by_id(self, contract_id: UUID) -> AgentContract | None:
        model = await self._get_model_by_id(contract_id)
        return agent_contract_model_to_entity(model) if model else None

    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentContract | None:
        result = await self._session.execute(
            select(AgentContractModel).where(
                AgentContractModel.agent_id == agent_id,
                AgentContractModel.version == version,
            )
        )
        model = result.scalar_one_or_none()
        return agent_contract_model_to_entity(model) if model else None

    async def list_by_agent(self, agent_id: UUID) -> list[AgentContract]:
        result = await self._session.execute(
            select(AgentContractModel)
            .where(AgentContractModel.agent_id == agent_id)
            .order_by(AgentContractModel.created_at.desc())
        )
        return [agent_contract_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentContract]:
        stmt = (
            select(AgentContractModel)
            .where(AgentContractModel.agent_id == agent_id)
            .order_by(AgentContractModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[agent_contract_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, contract_id: UUID) -> None:
        model = await self._get_model_by_id(contract_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyAgentModelConfigRepository(
    BaseSQLAlchemyRepository[AgentModelConfigModel],
    AgentModelConfigRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, AgentModelConfigModel)

    async def save(self, config: AgentModelConfig) -> AgentModelConfig:
        model = agent_model_config_entity_to_model(config)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return agent_model_config_model_to_entity(model)

    async def get_by_id(self, config_id: UUID) -> AgentModelConfig | None:
        model = await self._get_model_by_id(config_id)
        return agent_model_config_model_to_entity(model) if model else None

    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentModelConfig | None:
        result = await self._session.execute(
            select(AgentModelConfigModel).where(
                AgentModelConfigModel.agent_id == agent_id,
                AgentModelConfigModel.version == version,
            )
        )
        model = result.scalar_one_or_none()
        return agent_model_config_model_to_entity(model) if model else None

    async def list_by_agent(self, agent_id: UUID) -> list[AgentModelConfig]:
        result = await self._session.execute(
            select(AgentModelConfigModel)
            .where(AgentModelConfigModel.agent_id == agent_id)
            .order_by(AgentModelConfigModel.created_at.desc())
        )
        return [agent_model_config_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentModelConfig]:
        stmt = (
            select(AgentModelConfigModel)
            .where(AgentModelConfigModel.agent_id == agent_id)
            .order_by(AgentModelConfigModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[agent_model_config_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )


class SQLAlchemyAgentReleaseRepository(
    BaseSQLAlchemyRepository[AgentReleaseModel],
    AgentReleaseRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, AgentReleaseModel)

    async def save(self, release: AgentRelease) -> AgentRelease:
        existing = await self._get_model_by_id(release.id)
        if existing:
            new_model = agent_release_entity_to_model(release)
            for key, value in new_model.__dict__.items():
                if key in ("_sa_instance_state", "created_at", "updated_at"):
                    continue
                setattr(existing, key, value)
            await self._flush()
            await self._refresh_model(existing)
            return agent_release_model_to_entity(existing)
        model = agent_release_entity_to_model(release)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return agent_release_model_to_entity(model)

    async def get_by_id(self, release_id: UUID) -> AgentRelease | None:
        model = await self._get_model_by_id(release_id)
        return agent_release_model_to_entity(model) if model else None

    async def get_by_version(
        self, agent_id: UUID, version: str
    ) -> AgentRelease | None:
        result = await self._session.execute(
            select(AgentReleaseModel).where(
                AgentReleaseModel.agent_id == agent_id,
                AgentReleaseModel.version == version,
            )
        )
        model = result.scalar_one_or_none()
        return agent_release_model_to_entity(model) if model else None

    async def get_active_production(
        self, agent_id: UUID
    ) -> AgentRelease | None:
        result = await self._session.execute(
            select(AgentReleaseModel).where(
                AgentReleaseModel.agent_id == agent_id,
                AgentReleaseModel.status == "production",
            )
        )
        model = result.scalar_one_or_none()
        return agent_release_model_to_entity(model) if model else None

    async def list_by_agent(self, agent_id: UUID) -> list[AgentRelease]:
        result = await self._session.execute(
            select(AgentReleaseModel)
            .where(AgentReleaseModel.agent_id == agent_id)
            .order_by(AgentReleaseModel.created_at.desc())
        )
        return [agent_release_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentRelease]:
        stmt = (
            select(AgentReleaseModel)
            .where(AgentReleaseModel.agent_id == agent_id)
            .order_by(AgentReleaseModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[agent_release_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def list_by_status(
        self, agent_id: UUID, status: ReleaseStatus
    ) -> list[AgentRelease]:
        status_val = status.value if hasattr(status, "value") else status
        result = await self._session.execute(
            select(AgentReleaseModel)
            .where(
                AgentReleaseModel.agent_id == agent_id,
                AgentReleaseModel.status == status_val,
            )
            .with_for_update()
        )
        return [agent_release_model_to_entity(m) for m in result.scalars().all()]

    async def get_last_promoted(
        self, agent_id: UUID, *, exclude_id: UUID
    ) -> AgentRelease | None:
        result = await self._session.execute(
            select(AgentReleaseModel)
            .where(
                AgentReleaseModel.agent_id == agent_id,
                AgentReleaseModel.id != exclude_id,
                AgentReleaseModel.promoted_at.isnot(None),
            )
            .order_by(AgentReleaseModel.promoted_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return agent_release_model_to_entity(model) if model else None

    async def delete(self, release_id: UUID) -> None:
        model = await self._get_model_by_id(release_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyAgentReleaseTestRepository(
    BaseSQLAlchemyRepository[AgentReleaseTestModel],
    AgentReleaseTestRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, AgentReleaseTestModel)

    async def save(self, test: AgentReleaseTest) -> AgentReleaseTest:
        model = agent_release_test_entity_to_model(test)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return agent_release_test_model_to_entity(model)

    async def get_by_id(self, test_id: UUID) -> AgentReleaseTest | None:
        model = await self._get_model_by_id(test_id)
        return agent_release_test_model_to_entity(model) if model else None

    async def list_by_release(self, release_id: UUID) -> list[AgentReleaseTest]:
        result = await self._session.execute(
            select(AgentReleaseTestModel)
            .where(AgentReleaseTestModel.release_id == release_id)
            .order_by(AgentReleaseTestModel.created_at.desc())
        )
        return [agent_release_test_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_release(
        self, release_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentReleaseTest]:
        stmt = (
            select(AgentReleaseTestModel)
            .where(AgentReleaseTestModel.release_id == release_id)
            .order_by(AgentReleaseTestModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[agent_release_test_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )
