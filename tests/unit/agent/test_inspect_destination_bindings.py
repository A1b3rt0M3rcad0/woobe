import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.destination_binding_dtos import (
    InspectDestinationBindingsInput,
)
from modules.agent.application.use_cases.inspect_destination_bindings import (
    InspectDestinationBindingsUseCase,
)
from modules.agent.domain.entities import ProviderCredential, Secret
from modules.agent.domain.enums import Provider
from modules.agent.domain.vector_snapshot_entities import (
    VectorSnapshot,
    VECTOR_SNAPSHOT_READY,
)
from shared.contracts.errors import ValidationError, NotFoundError


@pytest.mark.asyncio
async def test_destination_inspection_never_decrypts_or_returns_protected_material():
    project = uuid4()
    credential = ProviderCredential(
        project_id=project,
        provider=Provider.openai_compatible,
        encrypted_secret="private-provider-value",
    )
    secret = Secret(
        project_id=project,
        name="service",
        encrypted_value="private-service-value",
        data={"secret": "private-service-value"},
    )
    snapshot = VectorSnapshot(
        project_id=project,
        collection_id=uuid4(),
        version="1.0.0",
        embedding_provider_model_id=uuid4(),
        embedding_provider="openai_compatible",
        embedding_model="embedding",
        status=VECTOR_SNAPSHOT_READY,
        snapshot_hash="immutable",
    )
    evidence = {"API_URL": {"id": str(uuid4()), "existing_key": "API_URL", "kind": "value",
                            "revision": "2026-10-06T00:00:00+00:00", "environments": {}}}
    environment = SimpleNamespace(require_keys=AsyncMock(), inspect_keys=AsyncMock(return_value=evidence))
    use_case = InspectDestinationBindingsUseCase(
        SimpleNamespace(get_by_id=AsyncMock(return_value=credential)),
        SimpleNamespace(get_by_name=AsyncMock(return_value=secret)),
        SimpleNamespace(get_by_id=AsyncMock(return_value=snapshot)),
        environment,
    )
    request = InspectDestinationBindingsInput.model_validate(
        {
            "project_id": project,
            "credentials": {
                "primary": {
                    "provider": "openai_compatible",
                    "credential_id": credential.id,
                }
            },
            "secrets": {"service": {"existing_key": "service"}},
            "project_environment": {"url": {"existing_key": "API_URL"}},
            "knowledge": {"docs": {"vector_snapshot_id": snapshot.id}},
        }
    )
    result = await use_case.execute(request)
    assert "private-" not in json.dumps(result)
    assert result["credentials"]["primary"]["credential_id"] == str(credential.id)
    assert result["knowledge"]["docs"]["snapshot_hash"] == "immutable"
    assert result["project_environment"]["url"] == evidence["API_URL"]
    environment.require_keys.assert_awaited_once_with(
        project_id=project, keys={"API_URL"}
    )
    request.project_environment["url"].kind = "secret"
    with pytest.raises(ValidationError, match="kind"):
        await use_case.execute(request)
    request.project_environment["url"].kind = "value"
    snapshot.status = "BUILDING"
    with pytest.raises(ValidationError, match="READY"):
        await use_case.execute(request)
    snapshot.status = VECTOR_SNAPSHOT_READY
    credential.project_id = uuid4()
    with pytest.raises(NotFoundError):
        await use_case.execute(request)


@pytest.mark.asyncio
async def test_knowledge_inspection_captures_embedding_model_and_provider_versions():
    from datetime import UTC, datetime, timedelta
    from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus
    project=uuid4();now=datetime.now(UTC)
    credential=SimpleNamespace(id=uuid4(),project_id=project,status=CredentialStatus.active,
        updated_at=now,created_at=now,encrypted_secret="never-return-this")
    model=SimpleNamespace(id=uuid4(),project_id=project,status=ProviderModelStatus.active,
        provider_credential_id=credential.id,updated_at=now,created_at=now,spec_hash="model-spec")
    snapshot=SimpleNamespace(id=uuid4(),project_id=project,status=VECTOR_SNAPSHOT_READY,
        snapshot_hash="vector-hash",collection_id=uuid4(),embedding_provider_model_id=model.id,
        updated_at=now,created_at=now)
    use_case=InspectDestinationBindingsUseCase(SimpleNamespace(get_by_id=AsyncMock(return_value=credential)),
        SimpleNamespace(),SimpleNamespace(get_by_id=AsyncMock(return_value=snapshot)),
        SimpleNamespace(require_keys=AsyncMock(),inspect_keys=AsyncMock(return_value={})),
        models=SimpleNamespace(get_by_id=AsyncMock(return_value=model)))
    request=InspectDestinationBindingsInput(project_id=project,knowledge={"docs":{"vector_snapshot_id":snapshot.id}})
    initial=await use_case.execute(request)
    assert initial["knowledge"]["docs"]["embedding_model"]["spec_hash"]=="model-spec"
    assert "never-return-this" not in json.dumps(initial)
    credential.updated_at=now+timedelta(seconds=1)
    changed=await use_case.execute(request)
    assert changed["knowledge"]["docs"]["embedding_model"]!=initial["knowledge"]["docs"]["embedding_model"]
    credential.status="revoked"
    with pytest.raises(ValidationError,match="credential must be active"):
        await use_case.execute(request)
    credential.status=CredentialStatus.active;model.project_id=uuid4()
    with pytest.raises(ValidationError,match="Model must be active"):
        await use_case.execute(request)
