from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.rotate_provider_credential_use_case import (
    RotateProviderCredentialUseCase,
)
from modules.agent.infra.adapters.model_discovery import (
    ModelDiscoveryContext,
    ModelDiscoveryService,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.rotate_provider_credential_controller import (
    RotateProviderCredentialController,
)
from shared.infra.config import Settings
from shared.domain.errors import ValidationError
from shared.infra.transactional_handler import TransactionalHandler


def rotate_provider_credential_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    settings = Settings.model_validate({})
    uow = AgentUnitOfWork(session_factory)
    discovery = ModelDiscoveryService()

    async def validate_secret(provider: str, secret: str, metadata: dict) -> None:
        try:
            models = await discovery.list_models(
                ModelDiscoveryContext(
                    provider=provider,
                    api_key=secret,
                    metadata=metadata,
                )
            )
        except Exception as exc:
            raise ValidationError(
                f"Unable to verify the new provider API key: {exc}"
            ) from exc
        if not models:
            raise ValidationError(
                "Unable to verify the new provider API key: provider returned no models"
            )

    use_case = RotateProviderCredentialUseCase(
        credential_repo=uow.provider_credentials,
        outbox=SQLAlchemyAgentOutboxEventWriter(uow),
        validate_secret=validate_secret,
        encryption_key=settings.encryption_key,
    )
    controller = RotateProviderCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)
