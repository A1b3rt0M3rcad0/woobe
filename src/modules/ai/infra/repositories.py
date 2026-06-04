from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.ai.domain.entities import Agent, ProviderCredential
from modules.ai.domain.repositories import (
    AgentRepository as AgentRepositoryInterface,
    ProviderCredentialRepository as ProviderCredentialRepositoryInterface,
)
from modules.ai.infra.mappers import (
    agent_entity_to_model,
    agent_model_to_entity,
    provider_credential_entity_to_model,
    provider_credential_model_to_entity,
)
from modules.ai.infra.models import (
    AgentModel,
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
            from modules.ai.domain.errors import AgentNotFoundError
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
