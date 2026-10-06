from copy import deepcopy
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.imported_model_dtos import ResolveImportedModelInput
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
)
from modules.agent.application.use_cases.resolve_imported_model import (
    ResolveImportedModelUseCase,
)
from modules.agent.domain.entities import ProviderCredential
from modules.agent.domain.enums import Provider
from shared.contracts.errors import ValidationError


@pytest.mark.asyncio
async def test_reuse_rechecks_full_identity_under_owner_locks_without_writing():
    credential = ProviderCredential(
        project_id=uuid4(),
        provider=Provider.openai_compatible,
        updated_at=datetime.now(UTC),
    )
    credentials = AsyncMock()
    credentials.get_by_id.return_value = credential
    credentials.lock_by_id.return_value = credential
    models = AsyncMock()
    creation = ResolveImportedModelInput(
        project_id=credential.project_id,
        provider_credential_id=credential.id,
        name="Imported",
        model="fake",
        expected_spec_hash="a" * 64,
    )
    model, _ = await CreateProviderModelUseCase(models, credentials).prepare(creation)
    model.updated_at = datetime.now(UTC)
    models.list_by_credential.return_value = [model]
    models.lock_by_id.return_value = model
    models.get_by_id.return_value = model
    approved = creation.model_copy(
        update={
            "expected_spec_hash": model.spec_hash,
            "expected_model_id": model.id,
            "expected_model_revision": model.updated_at.isoformat(),
            "expected_credential_revision": credential.updated_at.isoformat(),
        }
    )
    result = await ResolveImportedModelUseCase(models, credentials).execute(approved)
    assert result.id == model.id
    credentials.lock_by_id.assert_awaited_once_with(credential.id)
    models.lock_by_id.assert_awaited_once_with(model.id)
    models.save.assert_not_awaited()
    changed = deepcopy(model)
    changed.spec["pricing"] = {"currency": "BRL"}
    changed.spec_hash = None
    models.list_by_credential.return_value = [changed]
    with pytest.raises(ValidationError, match="identity changed"):
        await ResolveImportedModelUseCase(models, credentials).execute(approved)
    models.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_preserves_full_spec_and_rejects_rotated_destination_credential():
    credential = ProviderCredential(
        project_id=uuid4(),
        provider=Provider.openai_compatible,
        updated_at=datetime.now(UTC),
    )
    credentials = AsyncMock()
    credentials.get_by_id.return_value = credential
    credentials.lock_by_id.return_value = credential
    models = AsyncMock()
    models.list_by_credential.return_value = []
    models.save.side_effect = lambda model: model
    request = ResolveImportedModelInput(
        project_id=credential.project_id,
        provider_credential_id=credential.id,
        name="Imported",
        model="fake",
        expected_spec_hash="a" * 64,
    )
    prepared, _ = await CreateProviderModelUseCase(models, credentials).prepare(request)
    request.expected_spec_hash = prepared.spec_hash
    request.expected_credential_revision = credential.updated_at.isoformat()
    result = await ResolveImportedModelUseCase(models, credentials).execute(request)
    assert result.spec == prepared.spec and result.spec_hash == prepared.spec_hash
    credential.updated_at = datetime.now(UTC)
    with pytest.raises(ValidationError, match="credential changed"):
        await ResolveImportedModelUseCase(models, credentials).execute(request)
    assert models.save.await_count == 1
