from datetime import datetime, timezone
from typing import cast
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.agent.domain.entities import (
    Agent,
    AgentCollection,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    AskJob,
    Document,
    DocumentChunk,
    DocumentCollection,
    KnowledgeVersion,
    Message,
    ProviderCredential,
    Secret,
    Session,
    Tool,
)
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.events import AgentDomainEvent
from modules.agent.domain.errors import (
    AskJobNotFoundError,
    ChunkNotFoundError,
    CollectionNotFoundError,
    DocumentNotFoundError,
    MessageNotFoundError,
    SecretNotFoundError,
    SessionNotFoundError,
    ToolNotFoundError,
)
from modules.agent.application.interfaces.repositories import (
    AgentCollectionRepository,
    AgentContractRepository as AgentContractRepositoryInterface,
    AgentInboxRepository,
    AgentModelConfigRepository as AgentModelConfigRepositoryInterface,
    AgentOutboxRepository,
    AgentPromptRepository as AgentPromptRepositoryInterface,
    AgentReleaseRepository as AgentReleaseRepositoryInterface,
    AgentReleaseTestRepository as AgentReleaseTestRepositoryInterface,
    AgentRepository as AgentRepositoryInterface,
    AskJobRepository,
    DocumentChunkRepository,
    DocumentCollectionRepository,
    DocumentRepository,
    KnowledgeVersionRepository,
    MessageRepository,
    ProviderCredentialRepository as ProviderCredentialRepositoryInterface,
    SecretRepository,
    SessionRepository,
    ToolRepository,
)
from modules.agent.infra.database.mappers import (
    agent_collection_model_to_entity,
    agent_collection_to_model,
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
    ask_job_to_model,
    chunk_to_model,
    collection_to_model,
    document_to_model,
    knowledge_version_model_to_entity,
    knowledge_version_to_model,
    message_to_model,
    model_to_ask_job,
    model_to_chunk,
    model_to_collection,
    model_to_document,
    model_to_message,
    model_to_secret,
    model_to_session,
    model_to_tool,
    provider_credential_entity_to_model,
    provider_credential_model_to_entity,
    secret_to_model,
    session_to_model,
    tool_to_model,
)
from modules.agent.infra.database.models import (
    AgentCollectionModel,
    AgentContractModel,
    AgentInboxEventModel,
    AgentModel,
    AgentModelConfigModel,
    AgentOutboxEventModel,
    AgentPromptModel,
    AgentReleaseModel,
    AgentReleaseTestModel,
    AgentToolModel,
    AgentToolSecretModel,
    AskJobModel,
    DocumentChunkModel,
    DocumentCollectionModel,
    DocumentModel,
    KnowledgeVersionModel,
    MessageModel,
    ProviderCredentialModel,
    SessionModel,
)
from shared.contracts.pagination import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


class SQLAlchemyProviderCredentialRepository(
    BaseSQLAlchemyRepository[ProviderCredentialModel],
    ProviderCredentialRepositoryInterface,
):

    def __init__(self, session: UnitOfWork) -> None:
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

    def __init__(self, session: UnitOfWork) -> None:
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
        model.behavior_spec = agent.behavior_spec
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


class SQLAlchemyAgentPromptRepository(
    BaseSQLAlchemyRepository[AgentPromptModel],
    AgentPromptRepositoryInterface,
):

    def __init__(self, session: UnitOfWork) -> None:
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

    def __init__(self, session: UnitOfWork) -> None:
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

    def __init__(self, session: UnitOfWork) -> None:
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

    def __init__(self, session: UnitOfWork) -> None:
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

    def __init__(self, session: UnitOfWork) -> None:
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


class SQLAlchemyAgentCollectionRepository(AgentCollectionRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, AgentCollectionModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def list_by_agent(self, agent_id: UUID) -> list[AgentCollection]:
        stmt = (
            select(AgentCollectionModel)
            .where(AgentCollectionModel.agent_id == agent_id)
            .order_by(AgentCollectionModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [agent_collection_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentCollection]:
        stmt = (
            select(AgentCollectionModel)
            .where(AgentCollectionModel.agent_id == agent_id)
            .order_by(AgentCollectionModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[agent_collection_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def get_by_agent_and_collection(
        self, agent_id: UUID, collection_id: UUID
    ) -> AgentCollection | None:
        stmt = select(AgentCollectionModel).where(
            AgentCollectionModel.agent_id == agent_id,
            AgentCollectionModel.collection_id == collection_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return agent_collection_model_to_entity(model) if model else None

    async def list_by_collection(
        self, collection_id: UUID
    ) -> list[AgentCollection]:
        stmt = (
            select(AgentCollectionModel)
            .where(AgentCollectionModel.collection_id == collection_id)
            .order_by(AgentCollectionModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [
            agent_collection_model_to_entity(model)
            for model in result.scalars().all()
        ]

    async def create(self, link: AgentCollection) -> AgentCollection:
        model = agent_collection_to_model(link)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return agent_collection_model_to_entity(model)

    async def delete(self, link_id: UUID) -> None:
        model = await self._base._get_model_by_id(link_id)
        if model is None:
            raise CollectionNotFoundError(link_id)
        await self._base._delete_model(model)


class SQLAlchemyDocumentCollectionRepository(DocumentCollectionRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, DocumentCollectionModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, collection: DocumentCollection) -> DocumentCollection:
        model = collection_to_model(collection)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_collection(model)

    async def get_by_id(self, collection_id: UUID) -> DocumentCollection:
        model = await self._base._get_model_by_id(collection_id)
        if model is None or str(model.status).lower() == "deleted":
            raise CollectionNotFoundError(collection_id)
        return model_to_collection(model)

    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[DocumentCollection]:
        stmt = select(DocumentCollectionModel).where(
            DocumentCollectionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(DocumentCollectionModel.status == status)
        else:
            stmt = stmt.where(DocumentCollectionModel.status != "deleted")
        stmt = stmt.order_by(DocumentCollectionModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_collection(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[DocumentCollection]:
        stmt = select(DocumentCollectionModel).where(
            DocumentCollectionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(DocumentCollectionModel.status == status)
        else:
            stmt = stmt.where(DocumentCollectionModel.status != "deleted")
        stmt = stmt.order_by(DocumentCollectionModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_collection(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, collection: DocumentCollection) -> DocumentCollection:
        model = await self._base._get_model_by_id(collection.id)
        if model is None:
            raise CollectionNotFoundError(collection.id)
        model.name = collection.name
        model.description = collection.description
        model.status = collection.status
        return model_to_collection(model)

    async def delete(self, collection_id: UUID) -> None:
        model = await self._base._get_model_by_id(collection_id)
        if model is None:
            raise CollectionNotFoundError(collection_id)
        await self._base._delete_model(model)


class SQLAlchemyDocumentRepository(DocumentRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, DocumentModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, document: Document) -> Document:
        model = document_to_model(document)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_document(model)

    async def get_by_id(self, document_id: UUID) -> Document:
        model = await self._base._get_model_by_id(document_id)
        if model is None:
            raise DocumentNotFoundError(document_id)
        return model_to_document(model)

    async def list_by_collection(
        self, collection_id: UUID, status: str | None = None
    ) -> list[Document]:
        stmt = select(DocumentModel).where(
            DocumentModel.collection_id == collection_id
        )
        if status:
            stmt = stmt.where(DocumentModel.status == status)
        stmt = stmt.order_by(DocumentModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_document(m) for m in result.scalars().all()]

    async def list_by_project(self, project_id: UUID) -> list[Document]:
        stmt = select(DocumentModel).where(
            DocumentModel.project_id == project_id
        ).order_by(DocumentModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_document(m) for m in result.scalars().all()]

    async def paginate_by_collection(
        self, collection_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Document]:
        stmt = select(DocumentModel).where(
            DocumentModel.collection_id == collection_id
        )
        if status:
            stmt = stmt.where(DocumentModel.status == status)
        stmt = stmt.order_by(DocumentModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_document(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, document: Document) -> Document:
        model = await self._base._get_model_by_id(document.id)
        if model is None:
            raise DocumentNotFoundError(document.id)
        model.title = document.title
        model.file_name = document.file_name
        model.content_type = document.content_type
        model.size_bytes = document.size_bytes
        model.storage_key = document.storage_key
        model.parser = document.parser
        model.status = document.status
        model.error = document.error
        model.page_count = document.page_count
        model.chunk_count = document.chunk_count
        model.sha256 = document.sha256
        model.indexed_at = document.indexed_at
        return model_to_document(model)

    async def delete(self, document_id: UUID) -> None:
        model = await self._base._get_model_by_id(document_id)
        if model is None:
            raise DocumentNotFoundError(document_id)
        await self._base._delete_model(model)


class SQLAlchemyDocumentChunkRepository(DocumentChunkRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, DocumentChunkModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create_many(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        models = [chunk_to_model(c) for c in chunks]
        for m in models:
            await self._base._add_model(m)
        return [model_to_chunk(m) for m in models]

    async def get_by_id(self, chunk_id: UUID) -> DocumentChunk:
        model = await self._base._get_model_by_id(chunk_id)
        if model is None:
            raise ChunkNotFoundError(chunk_id)
        return model_to_chunk(model)

    async def list_by_document(
        self, document_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [model_to_chunk(m) for m in result.scalars().all()]

    async def paginate_by_document(
        self, document_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[DocumentChunk]:
        stmt = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_chunk(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete_by_document(self, document_id: UUID) -> None:
        stmt = select(DocumentChunkModel).where(
            DocumentChunkModel.document_id == document_id
        )
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            await self._base._delete_model(model)

    async def search_similar(
        self,
        embedding: list[float],
        collection_id: UUID,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[tuple[DocumentChunk, float]]:
        emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
        stmt = text(
            """
            SELECT id, 1 - (embedding <=> :embedding::vector) AS similarity
            FROM knowledge.document_chunks
            WHERE collection_id = :collection_id
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> :embedding::vector) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
            """
        )
        result = await self._session.execute(
            stmt,
            {
                "embedding": emb_str,
                "collection_id": collection_id,
                "threshold": threshold,
                "limit": limit,
            },
        )
        rows = result.fetchall()
        if not rows:
            return []

        chunk_ids = [row[0] for row in rows]
        similarity_map = {row[0]: row[1] for row in rows}

        chunks_stmt = select(DocumentChunkModel).where(
            DocumentChunkModel.id.in_(chunk_ids)
        )
        chunks_result = await self._session.execute(chunks_stmt)
        chunks = [model_to_chunk(m) for m in chunks_result.scalars().all()]
        chunks.sort(key=lambda c: similarity_map.get(c.id, 0), reverse=True)
        return [(c, similarity_map.get(c.id, 0.0)) for c in chunks]


class SQLAlchemyKnowledgeVersionRepository(KnowledgeVersionRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, KnowledgeVersionModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def save(self, version: KnowledgeVersion) -> KnowledgeVersion:
        model = knowledge_version_to_model(version)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return knowledge_version_model_to_entity(model)

    async def get_by_id(self, version_id: UUID) -> KnowledgeVersion | None:
        model = await self._base._get_model_by_id(version_id)
        return knowledge_version_model_to_entity(model) if model else None

    async def get_by_version(self, agent_id: UUID, version: str) -> KnowledgeVersion | None:
        stmt = select(KnowledgeVersionModel).where(
            KnowledgeVersionModel.agent_id == agent_id,
            KnowledgeVersionModel.version == version,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return knowledge_version_model_to_entity(model) if model else None

    async def list_by_agent(self, agent_id: UUID) -> list[KnowledgeVersion]:
        stmt = (
            select(KnowledgeVersionModel)
            .where(KnowledgeVersionModel.agent_id == agent_id)
            .order_by(KnowledgeVersionModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [knowledge_version_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_agent(self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None) -> CursorPage[KnowledgeVersion]:
        stmt = (
            select(KnowledgeVersionModel)
            .where(KnowledgeVersionModel.agent_id == agent_id)
            .order_by(KnowledgeVersionModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[knowledge_version_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )


class SQLAlchemySessionRepository(SessionRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, SessionModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, session: Session) -> Session:
        model = session_to_model(session)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_session(model)

    async def get_by_id(self, session_id: UUID) -> Session:
        model = await self._base._get_model_by_id(session_id)
        if model is None:
            raise SessionNotFoundError(session_id)
        return model_to_session(model)

    async def get_by_id_for_update(self, session_id: UUID) -> Session:
        model = await self._session.scalar(
            select(SessionModel)
            .where(SessionModel.id == session_id)
            .with_for_update()
        )
        if model is None:
            raise SessionNotFoundError(session_id)
        return model_to_session(model)

    async def get_by_external_id(
        self, project_id: UUID, agent_id: UUID, external_session_id: str
    ) -> Session:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id,
            SessionModel.agent_id == agent_id,
            SessionModel.external_session_id == external_session_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise SessionNotFoundError(session_id=external_session_id)
        return model_to_session(model)

    async def list_by_agent(
        self, project_id: UUID, agent_id: UUID, status: str | None = None
    ) -> list[Session]:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id,
            SessionModel.agent_id == agent_id,
        )
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.last_message_at.desc().nullslast())
        result = await self._session.execute(stmt)
        return [model_to_session(m) for m in result.scalars().all()]

    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Session]:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_session(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Session]:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_session(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, session: Session) -> Session:
        model = await self._base._get_model_by_id(session.id)
        if model is None:
            raise SessionNotFoundError(session.id)
        model.external_session_id = session.external_session_id
        model.tenant_id = session.tenant_id
        model.user_id = session.user_id
        model.status = session.status
        model.data = session.data
        model.external_context_snapshot = session.external_context_snapshot
        model.last_message_at = session.last_message_at
        return model_to_session(model)

    async def delete(self, session_id: UUID) -> None:
        model = await self._base._get_model_by_id(session_id)
        if model is None:
            raise SessionNotFoundError(session_id)
        await self._base._delete_model(model)


class SQLAlchemyMessageRepository(MessageRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, MessageModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, message: Message) -> Message:
        model = message_to_model(message)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_message(model)

    async def get_by_id(self, message_id: UUID) -> Message:
        model = await self._base._get_model_by_id(message_id)
        if model is None:
            raise MessageNotFoundError(message_id)
        return model_to_message(model)

    async def list_by_session(
        self, session_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[Message]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [model_to_message(m) for m in result.scalars().all()]

    async def paginate_by_session(
        self, session_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Message]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_message(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def count_by_session(self, session_id: UUID) -> int:
        stmt = select(func.count()).select_from(MessageModel).where(
            MessageModel.session_id == session_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_by_session(self, session_id: UUID) -> None:
        stmt = select(MessageModel).where(
            MessageModel.session_id == session_id
        )
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            await self._base._delete_model(model)


class SQLAlchemyAskJobRepository(AskJobRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, AskJobModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, job: AskJob) -> AskJob:
        model = ask_job_to_model(job)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_ask_job(model)

    async def get_by_id(self, job_id: UUID) -> AskJob:
        model = await self._base._get_model_by_id(job_id)
        if model is None:
            raise AskJobNotFoundError(job_id)
        return model_to_ask_job(model)

    async def list_pending(self, limit: int = 5) -> list[AskJob]:
        stmt = (
            select(AskJobModel)
            .where(AskJobModel.status == "pending")
            .order_by(AskJobModel.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [model_to_ask_job(m) for m in result.scalars().all()]

    async def mark_started(self, job_id: UUID) -> None:
        model = await self._base._get_model_by_id(job_id)
        if model:
            model.status = "running"
            model.started_at = datetime.now(timezone.utc)

    async def mark_waiting(
        self, job_id: UUID, result: dict, trace_id: UUID | None
    ) -> None:
        model = await self._base._get_model_by_id(job_id)
        if model:
            model.status = "waiting"
            model.result = result
            model.trace_id = trace_id
            model.completed_at = None

    async def mark_completed(
        self, job_id: UUID, result: dict, trace_id: UUID
    ) -> None:
        model = await self._base._get_model_by_id(job_id)
        if model:
            model.status = "completed"
            model.result = result
            model.trace_id = trace_id
            model.completed_at = datetime.now(timezone.utc)

    async def mark_failed(self, job_id: UUID, error: str) -> None:
        model = await self._base._get_model_by_id(job_id)
        if model:
            model.status = "failed"
            model.error = error
            model.completed_at = datetime.now(timezone.utc)


class SQLAlchemyAgentOutboxEventWriter:

    def __init__(self, session: UnitOfWork) -> None:
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def write(
        self,
        event: AgentDomainEvent,
    ) -> None:
        from modules.agent.infra.messaging.event_mappers import domain_event_to_outbox
        model = domain_event_to_outbox(event)
        self._session.add(model)


AGENT_OUTBOX_VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"publishing"},
    "publishing": {"published", "retryable", "dead"},
    "retryable": {"publishing"},
}

AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS: int = 300
AGENT_INBOX_LOCK_TIMEOUT_SECONDS: int = 300
AGENT_DEFAULT_BATCH_SIZE: int = 50


class SQLAlchemyAgentOutboxRepository(AgentOutboxRepository):
    def __init__(self, session: UnitOfWork) -> None:
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return cast(AsyncSession, self._session_or_uow)

    async def add(self, event: AgentOutboxEventModel) -> AgentOutboxEventModel:
        self._session.add(event)
        await self._session.flush()
        return event

    async def claim_batch(
        self,
        batch_size: int = AGENT_DEFAULT_BATCH_SIZE,
        locked_by: str = "",
        lock_timeout_seconds: int = AGENT_OUTBOX_LOCK_TIMEOUT_SECONDS,
    ) -> list[AgentOutboxEventModel]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(AgentOutboxEventModel)
            .where(AgentOutboxEventModel.status.in_(["pending", "retryable"]))
            .where(AgentOutboxEventModel.available_at <= func.now())
            .where(
                (AgentOutboxEventModel.locked_at.is_(None))
                | (
                    AgentOutboxEventModel.locked_at
                    < func.now() - text(f"INTERVAL '{lock_timeout_seconds} seconds'")
                )
            )
            .order_by(AgentOutboxEventModel.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        events = list(result.scalars().all())
        for event in events:
            event.status = "publishing"
            event.locked_at = now
            event.locked_by = locked_by
        await self._session.flush()
        return events

    async def mark_published(self, event_id: UUID) -> None:
        event = await self._session.get(AgentOutboxEventModel, event_id)
        if event is None:
            return
        self._validate_transition(event.status, "published")
        event.status = "published"
        event.published_at = datetime.now(timezone.utc)
        event.locked_at = None
        event.locked_by = None

    async def mark_retryable(
        self, event_id: UUID, error: str, available_at: datetime
    ) -> None:
        event = await self._session.get(AgentOutboxEventModel, event_id)
        if event is None:
            return
        self._validate_transition(event.status, "retryable")
        event.status = "retryable"
        event.attempts += 1
        event.error = error
        event.available_at = available_at
        event.locked_at = None
        event.locked_by = None

    async def mark_dead(self, event_id: UUID, error: str) -> None:
        event = await self._session.get(AgentOutboxEventModel, event_id)
        if event is None:
            return
        self._validate_transition(event.status, "dead")
        event.status = "dead"
        event.attempts += 1
        event.error = error
        event.locked_at = None
        event.locked_by = None

    @staticmethod
    def _validate_transition(current: str, target: str) -> None:
        allowed = AGENT_OUTBOX_VALID_TRANSITIONS.get(current)
        if allowed is None or target not in allowed:
            raise ValueError(
                f"Invalid outbox status transition: {current} -> {target}"
            )


AGENT_INBOX_VALID_TRANSITIONS: dict[str, set[str]] = {
    "received": {"processing", "ignored"},
    "processing": {"processed", "retryable", "dead"},
    "retryable": {"processing"},
}


class SQLAlchemyAgentInboxRepository(AgentInboxRepository):
    def __init__(self, session: UnitOfWork) -> None:
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return cast(AsyncSession, self._session_or_uow)

    async def save_received(self, event: AgentInboxEventModel) -> AgentInboxEventModel:
        self._session.add(event)
        await self._session.flush()
        return event

    async def claim_batch(
        self,
        batch_size: int = AGENT_DEFAULT_BATCH_SIZE,
        locked_by: str = "",
        lock_timeout_seconds: int = AGENT_INBOX_LOCK_TIMEOUT_SECONDS,
    ) -> list[AgentInboxEventModel]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(AgentInboxEventModel)
            .where(AgentInboxEventModel.status.in_(["received", "retryable"]))
            .where(AgentInboxEventModel.available_at <= func.now())
            .where(
                (AgentInboxEventModel.locked_at.is_(None))
                | (
                    AgentInboxEventModel.locked_at
                    < func.now() - text(f"INTERVAL '{lock_timeout_seconds} seconds'")
                )
            )
            .order_by(AgentInboxEventModel.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self._session.execute(stmt)
        events = list(result.scalars().all())
        for event in events:
            event.locked_at = now
            event.locked_by = locked_by
            event.status = "processing"
            event.attempts += 1
        await self._session.flush()
        return events

    async def mark_processing(self, event_id: UUID, locked_by: str) -> None:
        event = await self._session.get(AgentInboxEventModel, event_id)
        if event is None:
            return
        self._validate_transition(event.status, "processing")
        event.status = "processing"
        event.locked_at = datetime.now(timezone.utc)
        event.locked_by = locked_by
        event.attempts += 1

    async def mark_processed(self, event_id: UUID) -> None:
        event = await self._session.get(AgentInboxEventModel, event_id)
        if event is None:
            return
        self._validate_transition(event.status, "processed")
        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        event.locked_at = None
        event.locked_by = None

    async def mark_retryable(
        self, event_id: UUID, error: str, available_at: datetime
    ) -> None:
        event = await self._session.get(AgentInboxEventModel, event_id)
        if event is None:
            return
        self._validate_transition(event.status, "retryable")
        event.status = "retryable"
        event.error = error
        event.available_at = available_at
        event.locked_at = None
        event.locked_by = None

    async def mark_dead(self, event_id: UUID, error: str) -> None:
        event = await self._session.get(AgentInboxEventModel, event_id)
        if event is None:
            return
        self._validate_transition(event.status, "dead")
        event.status = "dead"
        event.error = error
        event.locked_at = None
        event.locked_by = None

    async def mark_ignored(self, event_id: UUID, reason: str) -> None:
        event = await self._session.get(AgentInboxEventModel, event_id)
        if event is None:
            return
        self._validate_transition(event.status, "ignored")
        event.status = "ignored"
        event.error = reason
        event.locked_at = None
        event.locked_by = None

    @staticmethod
    def _validate_transition(current: str, target: str) -> None:
        allowed = AGENT_INBOX_VALID_TRANSITIONS.get(current)
        if allowed is None or target not in allowed:
            raise ValueError(
                f"Invalid inbox status transition: {current} -> {target}"
            )


class SQLAlchemyAgentToolRepository(ToolRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, AgentToolModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, tool: Tool) -> Tool:
        model = tool_to_model(tool)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_tool(model)

    async def get_by_id(self, tool_id: UUID) -> Tool:
        model = await self._base._get_model_by_id(tool_id)
        if model is None:
            raise ToolNotFoundError(tool_id)
        return model_to_tool(model)

    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Tool]:
        stmt = select(AgentToolModel).where(AgentToolModel.project_id == project_id)
        if status:
            stmt = stmt.where(AgentToolModel.status == status)
        stmt = stmt.order_by(AgentToolModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_tool(m) for m in result.scalars().all()]

    async def list_by_agent(
        self, agent_id: UUID, status: str | None = None
    ) -> list[Tool]:
        stmt = select(AgentToolModel).where(AgentToolModel.agent_id == agent_id)
        if status:
            stmt = stmt.where(AgentToolModel.status == status)
        stmt = stmt.order_by(AgentToolModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_tool(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Tool]:
        stmt = select(AgentToolModel).where(AgentToolModel.project_id == project_id)
        if status:
            stmt = stmt.where(AgentToolModel.status == status)
        stmt = stmt.order_by(AgentToolModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_tool(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def paginate_by_agent(
        self, agent_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Tool]:
        stmt = select(AgentToolModel).where(AgentToolModel.agent_id == agent_id)
        if status:
            stmt = stmt.where(AgentToolModel.status == status)
        stmt = stmt.order_by(AgentToolModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_tool(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, tool: Tool) -> Tool:
        model = await self._base._get_model_by_id(tool.id)
        if model is None:
            raise ToolNotFoundError(tool.id)
        model.name = tool.name
        model.description = tool.description
        model.agent_id = tool.agent_id
        model.type = tool.type.value if hasattr(tool.type, 'value') else tool.type
        model.config = tool.config
        model.input_schema = tool.input_schema
        model.output_schema = tool.output_schema
        model.risk_level = tool.risk_level.value if hasattr(tool.risk_level, 'value') else tool.risk_level
        model.timeout_ms = tool.timeout_ms
        model.status = tool.status.value if hasattr(tool.status, 'value') else tool.status
        return model_to_tool(model)

    async def delete(self, tool_id: UUID) -> None:
        model = await self._base._get_model_by_id(tool_id)
        if model is None:
            raise ToolNotFoundError(tool_id)
        await self._base._delete_model(model)


class SQLAlchemyAgentToolSecretRepository(SecretRepository):

    def __init__(self, session: UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, AgentToolSecretModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, secret: Secret) -> Secret:
        model = secret_to_model(secret)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_secret(model)

    async def get_by_id(self, secret_id: UUID) -> Secret:
        model = await self._base._get_model_by_id(secret_id)
        if model is None:
            raise SecretNotFoundError(secret_id)
        return model_to_secret(model)

    async def get_by_name(self, project_id: UUID, name: str) -> Secret:
        stmt = select(AgentToolSecretModel).where(
            AgentToolSecretModel.project_id == project_id,
            AgentToolSecretModel.name == name,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise SecretNotFoundError(secret_id=name)
        return model_to_secret(model)

    async def list_by_project(self, project_id: UUID) -> list[Secret]:
        stmt = (
            select(AgentToolSecretModel)
            .where(AgentToolSecretModel.project_id == project_id)
            .order_by(AgentToolSecretModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [model_to_secret(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Secret]:
        stmt = (
            select(AgentToolSecretModel)
            .where(AgentToolSecretModel.project_id == project_id)
            .order_by(AgentToolSecretModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_secret(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, secret: Secret) -> Secret:
        model = await self._base._get_model_by_id(secret.id)
        if model is None:
            raise SecretNotFoundError(secret.id)
        model.name = secret.name
        model.type = secret.type.value if hasattr(secret.type, 'value') else secret.type
        model.encrypted_value = secret.encrypted_value
        model.data = secret.data
        return model_to_secret(model)

    async def delete(self, secret_id: UUID) -> None:
        model = await self._base._get_model_by_id(secret_id)
        if model is None:
            raise SecretNotFoundError(secret_id)
        await self._base._delete_model(model)