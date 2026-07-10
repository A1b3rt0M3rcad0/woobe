from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import uuid6

from modules.agent.application.dtos.provider_credential_rotation_dtos import (
    RotateProviderCredentialInput,
    RotateProviderCredentialOutput,
)
from modules.agent.domain.credential_events import AgentProviderCredentialRotatedV1
from modules.agent.domain.enums import CredentialStatus
from modules.agent.domain.repositories import ProviderCredentialRepository
from shared.infra.crypto import encrypt_secret
from shared.infra.errors import ConflictError, ValidationError
from shared.messaging.outbox_writer import OutboxEventWriter


ProviderCredentialValidator = Callable[[str, str, dict], Awaitable[None]]


class RotateProviderCredentialUseCase:
    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
        validate_secret: ProviderCredentialValidator,
        encryption_key: str,
    ) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._validate_secret = validate_secret
        self._encryption_key = encryption_key

    async def execute(
        self,
        credential_id,
        input_dto: RotateProviderCredentialInput,
    ) -> RotateProviderCredentialOutput:
        credential = await self._credential_repo.get_by_id(credential_id)
        if credential is None or credential.project_id != input_dto.project_id:
            from modules.agent.domain.errors import CredentialNotFoundError

            raise CredentialNotFoundError(credential_id)

        status = getattr(credential.status, "value", credential.status)
        if status != CredentialStatus.active.value:
            raise ConflictError("Only active provider credentials can be rotated")

        secret = input_dto.secret.strip()
        if not secret:
            raise ValidationError("New provider API key is required")

        provider = getattr(credential.provider, "value", credential.provider)
        await self._validate_secret(provider, secret, credential.metadata or {})

        rotated_at = datetime.now(UTC)
        operation_id = uuid6.uuid7()
        credential.encrypted_secret = encrypt_secret(secret, self._encryption_key)
        credential.last_validated_at = rotated_at
        saved = await self._credential_repo.update(credential)

        await self._outbox.write(
            AgentProviderCredentialRotatedV1.create(
                credential_id=saved.id,
                project_id=saved.project_id,
                provider=str(provider),
                rotated_by_user_id=input_dto.rotated_by_user_id,
                rotated_at=rotated_at,
                operation_id=operation_id,
            )
        )

        return RotateProviderCredentialOutput(
            id=saved.id,
            project_id=saved.project_id,
            provider=saved.provider,
            name=saved.name,
            status=saved.status,
            last_validated_at=saved.last_validated_at,
            updated_at=saved.updated_at,
            metadata=saved.metadata,
        )
