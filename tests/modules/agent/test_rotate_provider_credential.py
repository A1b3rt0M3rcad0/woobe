from uuid import uuid4

import pytest

from modules.agent.application.dtos.provider_credential_rotation_dtos import (
    RotateProviderCredentialInput,
)
from modules.agent.application.use_cases.rotate_provider_credential_use_case import (
    RotateProviderCredentialUseCase,
)
from modules.agent.domain.entities import ProviderCredential
from modules.agent.domain.enums import CredentialStatus, Provider
from shared.infra.crypto import decrypt_secret, encrypt_secret
from shared.infra.errors import ConflictError, ValidationError


class FakeCredentialRepository:
    def __init__(self, credential: ProviderCredential) -> None:
        self.credential = credential
        self.update_calls = 0

    async def get_by_id(self, credential_id):
        if credential_id != self.credential.id:
            return None
        return self.credential

    async def update(self, credential: ProviderCredential) -> ProviderCredential:
        self.update_calls += 1
        self.credential = credential
        return credential


class FakeOutbox:
    def __init__(self) -> None:
        self.events = []

    async def write(self, event) -> None:
        self.events.append(event)


def build_credential(*, encryption_key: str, status: CredentialStatus = CredentialStatus.active) -> ProviderCredential:
    return ProviderCredential(
        id=uuid4(),
        project_id=uuid4(),
        provider=Provider.openai,
        name="OpenAI",
        encrypted_secret=encrypt_secret("old-secret", encryption_key),
        status=status,
        metadata={"provider_family": "openai"},
    )


@pytest.mark.asyncio
async def test_rotates_secret_in_place_after_successful_verification() -> None:
    encryption_key = "test-encryption-key"
    credential = build_credential(encryption_key=encryption_key)
    repo = FakeCredentialRepository(credential)
    outbox = FakeOutbox()
    verification_calls = []

    async def validate_secret(provider: str, secret: str, metadata: dict) -> None:
        verification_calls.append((provider, secret, metadata))

    use_case = RotateProviderCredentialUseCase(
        credential_repo=repo,
        outbox=outbox,
        validate_secret=validate_secret,
        encryption_key=encryption_key,
    )

    result = await use_case.execute(
        credential.id,
        RotateProviderCredentialInput(
            project_id=credential.project_id,
            secret="new-secret",
            rotated_by_user_id=uuid4(),
        ),
    )

    assert result.id == credential.id
    assert repo.update_calls == 1
    assert decrypt_secret(repo.credential.encrypted_secret, encryption_key) == "new-secret"
    assert repo.credential.last_validated_at is not None
    assert verification_calls == [("openai", "new-secret", credential.metadata)]
    assert len(outbox.events) == 1
    assert outbox.events[0].event_type == "agent.credential.rotated.v1"
    assert outbox.events[0].payload["credential_id"] == str(credential.id)


@pytest.mark.asyncio
async def test_keeps_current_secret_when_verification_fails() -> None:
    encryption_key = "test-encryption-key"
    credential = build_credential(encryption_key=encryption_key)
    original_secret = credential.encrypted_secret
    repo = FakeCredentialRepository(credential)
    outbox = FakeOutbox()

    async def validate_secret(provider: str, secret: str, metadata: dict) -> None:
        raise ValidationError("Provider rejected the key")

    use_case = RotateProviderCredentialUseCase(
        credential_repo=repo,
        outbox=outbox,
        validate_secret=validate_secret,
        encryption_key=encryption_key,
    )

    with pytest.raises(ValidationError, match="Provider rejected the key"):
        await use_case.execute(
            credential.id,
            RotateProviderCredentialInput(
                project_id=credential.project_id,
                secret="invalid-secret",
                rotated_by_user_id=uuid4(),
            ),
        )

    assert repo.update_calls == 0
    assert repo.credential.encrypted_secret == original_secret
    assert outbox.events == []


@pytest.mark.asyncio
async def test_rejects_rotation_for_non_active_credential() -> None:
    encryption_key = "test-encryption-key"
    credential = build_credential(
        encryption_key=encryption_key,
        status=CredentialStatus.revoked,
    )
    repo = FakeCredentialRepository(credential)
    outbox = FakeOutbox()

    async def validate_secret(provider: str, secret: str, metadata: dict) -> None:
        raise AssertionError("verification must not run")

    use_case = RotateProviderCredentialUseCase(
        credential_repo=repo,
        outbox=outbox,
        validate_secret=validate_secret,
        encryption_key=encryption_key,
    )

    with pytest.raises(ConflictError, match="Only active provider credentials"):
        await use_case.execute(
            credential.id,
            RotateProviderCredentialInput(
                project_id=credential.project_id,
                secret="new-secret",
                rotated_by_user_id=uuid4(),
            ),
        )

    assert repo.update_calls == 0
    assert outbox.events == []
