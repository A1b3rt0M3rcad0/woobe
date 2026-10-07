from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import (
    CreateProviderCredentialInput,
    CreateProviderModelInput,
    ListProviderCredentialsInput,
    ListProviderModelsInput,
    UpdateProviderCredentialInput,
    UpdateProviderModelInput,
)
from modules.agent.application.use_cases import (
    ArchiveProviderCredentialUseCase,
    ArchiveProviderModelUseCase,
    CreateProviderCredentialUseCase,
    CreateProviderModelUseCase,
    GetProviderModelUseCase,
    ListProviderCredentialsUseCase,
    ListProviderModelsUseCase,
    RevokeProviderCredentialUseCase,
    RotateProviderCredentialUseCase,
    UpdateProviderCredentialUseCase,
    UpdateProviderModelUseCase,
)
from modules.agent.application.use_cases import ai_credential_cases, provider_management_cases
from modules.agent.domain.entities import ProviderCredential, ProviderModel
from modules.agent.domain.enums import CredentialStatus, Provider, ProviderModelStatus
from modules.agent.domain.errors import CredentialNotFoundError, ModelConfigNotFoundError
from shared.infra.errors import ConflictError, ValidationError


def _credential(
    *,
    project_id,
    credential_id=None,
    status=CredentialStatus.active,
    name="OpenAI",
    metadata=None,
):
    return ProviderCredential(
        id=credential_id or uuid4(),
        project_id=project_id,
        provider=Provider.openai,
        name=name,
        encrypted_secret="ciphertext",
        status=status,
        metadata=metadata or {},
    )


def _model(
    *,
    project_id,
    credential_id,
    model_id=None,
    name="GPT",
    model="gpt-test",
    status=ProviderModelStatus.active,
    metadata=None,
):
    return ProviderModel(
        id=model_id or uuid4(),
        project_id=project_id,
        provider_credential_id=credential_id,
        name=name,
        model=model,
        status=status,
        metadata=metadata or {},
    )


def _passthrough(mock):
    async def _call(value):
        return value

    mock.side_effect = _call


@pytest.mark.asyncio
async def test_embedding_only_model_blocks_archival_and_credential_usage_includes_knowledge():
    project_id, credential_id, model_id, vector_id = uuid4(), uuid4(), uuid4(), uuid4()
    credential = _credential(project_id=project_id, credential_id=credential_id)
    model = _model(project_id=project_id, credential_id=credential_id, model_id=model_id)
    models = SimpleNamespace(get_by_id=AsyncMock(return_value=model), list_by_credential=AsyncMock(return_value=[model]), update=AsyncMock())
    credentials = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))
    agents = SimpleNamespace(list_by_project=AsyncMock(return_value=[]))
    releases = SimpleNamespace(list_by_agent=AsyncMock(return_value=[]))
    dependency = {"type":"vector_snapshot", "id":str(vector_id), "field":"embedding_provider_model_id", "name":"Knowledge", "status":"READY"}
    dependencies = SimpleNamespace(embedding_consumers=AsyncMock(return_value=[dependency]), downstream_consumers=AsyncMock(return_value=[]))
    usage = provider_management_cases.ProviderModelUsageUseCase(models, agents, releases, dependency_reader=dependencies)
    result = await usage.execute(model_id)
    assert result["blocking"] == [dependency]
    assert result["can_delete"] is False
    dependencies.embedding_consumers.assert_awaited_with(project_id, {model_id})
    with pytest.raises(ConflictError, match="still in use"):
        await ArchiveProviderModelUseCase(models, usage).execute(model_id)
    models.update.assert_not_awaited()
    credential_usage = provider_management_cases.ProviderCredentialUsageUseCase(credentials, models, agents, releases, dependency_reader=dependencies)
    result = await credential_usage.execute(credential_id)
    assert dependency in result["blocking"]
    dependencies.embedding_consumers.assert_awaited_with(project_id, {model_id})


@pytest.mark.asyncio
async def test_create_provider_credential_encrypts_secret_and_emits_event(monkeypatch):
    project_id = uuid4()
    repo = SimpleNamespace(save=AsyncMock())
    _passthrough(repo.save)
    outbox = SimpleNamespace(write=AsyncMock())
    encrypt = lambda secret, key: f"enc:{key}:{secret}"
    monkeypatch.setattr(ai_credential_cases, "encrypt_secret", encrypt)

    result = await CreateProviderCredentialUseCase(
        repo,
        outbox,
        encryption_key="key-1",
    ).execute(
        CreateProviderCredentialInput(
            project_id=project_id,
            provider=Provider.openai,
            name="OpenAI",
            secret="plain-key",
            metadata={"owner": "team"},
        )
    )

    persisted = repo.save.await_args.args[0]
    assert persisted.encrypted_secret == "enc:key-1:plain-key"
    assert persisted.encrypted_secret != "plain-key"
    assert result.name == "OpenAI"
    assert result.metadata == {"owner": "team"}
    assert not hasattr(result, "secret")
    event = outbox.write.await_args.args[0]
    assert event.event_type == "agent.credential.created.v1"
    assert event.payload["credential_id"] == str(persisted.id)
    assert "plain-key" not in str(event.payload)


@pytest.mark.asyncio
async def test_update_provider_credential_reencrypts_secret_without_persisting_plaintext(monkeypatch):
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=credential),
        update=AsyncMock(),
    )
    _passthrough(repo.update)
    outbox = SimpleNamespace(write=AsyncMock())
    monkeypatch.setattr(
        ai_credential_cases,
        "encrypt_secret",
        lambda secret, key: f"enc:{secret}",
    )

    result = await UpdateProviderCredentialUseCase(
        repo,
        outbox,
        encryption_key="key-1",
    ).execute(
        credential.id,
        UpdateProviderCredentialInput(
            name="OpenAI rotated",
            secret="new-secret",
            metadata={"rotated": True},
        ),
    )

    assert credential.name == "OpenAI rotated"
    assert credential.encrypted_secret == "enc:new-secret"
    assert credential.metadata == {"rotated": True}
    assert result.name == "OpenAI rotated"
    repo.update.assert_awaited_once_with(credential)
    event = outbox.write.await_args.args[0]
    assert event.event_type == "agent.credential.updated.v1"
    assert "new-secret" not in str(event.payload)


@pytest.mark.asyncio
async def test_update_provider_credential_not_found_is_explicit():
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None), update=AsyncMock())
    outbox = SimpleNamespace(write=AsyncMock())

    with pytest.raises(CredentialNotFoundError):
        await UpdateProviderCredentialUseCase(repo, outbox, encryption_key="key").execute(
            uuid4(),
            UpdateProviderCredentialInput(name="missing"),
        )

    repo.update.assert_not_awaited()
    outbox.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_provider_credentials_preserves_project_scope():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    repo = SimpleNamespace(list_by_project=AsyncMock(return_value=[credential]))
    use_case = ListProviderCredentialsUseCase(repo)

    assert await use_case.execute(ListProviderCredentialsInput(project_id=None)) == []
    repo.list_by_project.assert_not_awaited()

    result = await use_case.execute(ListProviderCredentialsInput(project_id=project_id))
    repo.list_by_project.assert_awaited_once_with(project_id)
    assert len(result) == 1
    assert result[0].id == credential.id
    assert result[0].provider == Provider.openai


@pytest.mark.asyncio
async def test_create_provider_model_requires_active_same_project_credential_and_trims_fields():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    model_repo = SimpleNamespace(save=AsyncMock())
    _passthrough(model_repo.save)
    credential_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))

    result = await CreateProviderModelUseCase(model_repo, credential_repo).execute(
        CreateProviderModelInput(
            project_id=project_id,
            provider_credential_id=credential.id,
            name="  Main GPT  ",
            model="  gpt-test  ",
            metadata={"capability": "chat"},
        )
    )

    persisted = model_repo.save.await_args.args[0]
    assert persisted.name == "Main GPT"
    assert persisted.model == "gpt-test"
    assert persisted.status == ProviderModelStatus.active
    assert result.provider == Provider.openai


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "credential, expected_error",
    [
        (None, CredentialNotFoundError),
        ("other-project", CredentialNotFoundError),
        ("inactive", ValidationError),
    ],
)
async def test_create_provider_model_rejects_invalid_credential_state(credential, expected_error):
    project_id = uuid4()
    if credential == "other-project":
        credential = _credential(project_id=uuid4())
    elif credential == "inactive":
        credential = _credential(project_id=project_id, status=CredentialStatus.revoked)
    credential_id = credential.id if credential is not None else uuid4()
    model_repo = SimpleNamespace(save=AsyncMock())
    credential_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))

    with pytest.raises(expected_error):
        await CreateProviderModelUseCase(model_repo, credential_repo).execute(
            CreateProviderModelInput(
                project_id=project_id,
                provider_credential_id=credential_id,
                name="Model",
                model="gpt-test",
            )
        )

    model_repo.save.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name, model, message",
    [
        ("   ", "gpt-test", "name is required"),
        ("GPT", "   ", "identifier is required"),
    ],
)
async def test_create_provider_model_rejects_blank_normalized_fields(name, model, message):
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    model_repo = SimpleNamespace(save=AsyncMock())
    credential_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))

    with pytest.raises(ValidationError, match=message):
        await CreateProviderModelUseCase(model_repo, credential_repo).execute(
            CreateProviderModelInput(
                project_id=project_id,
                provider_credential_id=credential.id,
                name=name,
                model=model,
            )
        )


@pytest.mark.asyncio
async def test_update_provider_model_can_rebind_credential_and_update_metadata_status():
    project_id = uuid4()
    old_credential = _credential(project_id=project_id)
    new_credential = _credential(project_id=project_id)
    item = _model(project_id=project_id, credential_id=old_credential.id)
    model_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        update=AsyncMock(),
    )
    _passthrough(model_repo.update)
    credential_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=new_credential))

    result = await UpdateProviderModelUseCase(model_repo, credential_repo).execute(
        item.id,
        UpdateProviderModelInput(
            provider_credential_id=new_credential.id,
            name="  Updated  ",
            model="  updated-model  ",
            metadata={"tier": "premium"},
            status=ProviderModelStatus.inactive,
        ),
    )

    assert item.provider_credential_id == new_credential.id
    assert item.name == "Updated"
    assert item.model == "updated-model"
    assert item.metadata == {"tier": "premium"}
    assert item.status == ProviderModelStatus.inactive
    assert result.provider == Provider.openai


@pytest.mark.asyncio
async def test_update_provider_model_not_found_is_explicit():
    model_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=None), update=AsyncMock())
    credential_repo = SimpleNamespace(get_by_id=AsyncMock())

    with pytest.raises(ModelConfigNotFoundError):
        await UpdateProviderModelUseCase(model_repo, credential_repo).execute(
            uuid4(),
            UpdateProviderModelInput(name="missing"),
        )

    model_repo.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_provider_models_selects_credential_or_project_scope_and_caches_credentials():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    first = _model(project_id=project_id, credential_id=credential.id, name="A")
    second = _model(project_id=project_id, credential_id=credential.id, name="B")
    model_repo = SimpleNamespace(
        list_by_credential=AsyncMock(return_value=[first, second]),
        list_by_project=AsyncMock(return_value=[first, second]),
    )
    credential_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))
    use_case = ListProviderModelsUseCase(model_repo, credential_repo)

    assert await use_case.execute(ListProviderModelsInput()) == []

    by_credential = await use_case.execute(
        ListProviderModelsInput(provider_credential_id=credential.id)
    )
    assert len(by_credential) == 2
    model_repo.list_by_credential.assert_awaited_once_with(credential.id)
    assert credential_repo.get_by_id.await_count == 1

    credential_repo.get_by_id.reset_mock()
    by_project = await use_case.execute(ListProviderModelsInput(project_id=project_id))
    assert len(by_project) == 2
    model_repo.list_by_project.assert_awaited_once_with(project_id)
    assert credential_repo.get_by_id.await_count == 1


@pytest.mark.asyncio
async def test_get_provider_model_returns_provider_and_not_found_is_explicit():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    item = _model(project_id=project_id, credential_id=credential.id)
    model_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=item))
    credential_repo = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))
    use_case = GetProviderModelUseCase(model_repo, credential_repo)

    result = await use_case.execute(item.id)
    assert result.id == item.id
    assert result.provider == Provider.openai

    model_repo.get_by_id.return_value = None
    with pytest.raises(ModelConfigNotFoundError):
        await use_case.execute(uuid4())


@pytest.mark.asyncio
async def test_rotate_provider_credential_requires_secret_and_tracks_rotation_metadata(monkeypatch):
    project_id = uuid4()
    credential = _credential(
        project_id=project_id,
        metadata={"rotated_at": "old", "rotation_count": 2},
    )
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=credential),
        update=AsyncMock(),
    )
    _passthrough(repo.update)
    monkeypatch.setattr(
        provider_management_cases,
        "encrypt_secret",
        lambda secret, key: f"rotated:{secret}",
    )
    use_case = RotateProviderCredentialUseCase(repo, encryption_key="key")

    with pytest.raises(ValidationError, match="New API key is required"):
        await use_case.execute(credential.id, {"secret": "   "})

    result = await use_case.execute(
        credential.id,
        {"secret": "new-key", "expires_at": "2030-01-01T00:00:00+00:00"},
    )

    assert result.encrypted_secret == "rotated:new-key"
    assert result.status == CredentialStatus.active
    assert result.metadata["previous_rotated_at"] == "old"
    assert result.metadata["rotation_count"] == 3
    assert result.metadata["expires_at"] == "2030-01-01T00:00:00+00:00"
    assert result.metadata["rotated_at"] != "old"


@pytest.mark.asyncio
async def test_archived_credential_cannot_be_rotated():
    project_id = uuid4()
    credential = _credential(project_id=project_id, status=CredentialStatus.archived)
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=credential), update=AsyncMock())

    with pytest.raises(ValidationError, match="Archived credential cannot be rotated"):
        await RotateProviderCredentialUseCase(repo, encryption_key="key").execute(
            credential.id,
            {"secret": "new-key"},
        )

    repo.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_revoke_provider_credential_records_reason_and_timestamp():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=credential),
        update=AsyncMock(),
    )
    _passthrough(repo.update)

    result = await RevokeProviderCredentialUseCase(repo).execute(
        credential.id,
        {"reason": "compromised"},
    )

    assert result.status == CredentialStatus.revoked
    assert result.metadata["revoked_reason"] == "compromised"
    assert "revoked_at" in result.metadata


@pytest.mark.asyncio
async def test_archive_provider_credential_blocks_usage_and_soft_deletes_when_free():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=credential),
        update=AsyncMock(),
    )
    _passthrough(repo.update)
    usage = SimpleNamespace(execute=AsyncMock(return_value={"can_delete": False}))
    use_case = ArchiveProviderCredentialUseCase(repo, usage)

    with pytest.raises(ConflictError, match="still in use"):
        await use_case.execute(credential.id)
    repo.update.assert_not_awaited()

    usage.execute.return_value = {"can_delete": True}
    result = await use_case.execute(credential.id)
    assert result.status == CredentialStatus.archived
    assert result.metadata["delete_mode"] == "soft_delete"
    assert "deleted_at" in result.metadata


@pytest.mark.asyncio
async def test_archive_provider_model_blocks_usage_and_soft_deletes_when_free():
    project_id = uuid4()
    credential = _credential(project_id=project_id)
    item = _model(project_id=project_id, credential_id=credential.id)
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=item),
        update=AsyncMock(),
    )
    _passthrough(repo.update)
    usage = SimpleNamespace(execute=AsyncMock(return_value={"can_delete": False}))
    use_case = ArchiveProviderModelUseCase(repo, usage)

    with pytest.raises(ConflictError, match="still in use"):
        await use_case.execute(item.id)
    repo.update.assert_not_awaited()

    usage.execute.return_value = {"can_delete": True}
    result = await use_case.execute(item.id)
    assert result.status == ProviderModelStatus.archived
    assert result.metadata["delete_mode"] == "soft_delete"
    assert "deleted_at" in result.metadata
