from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.vector_snapshot_dtos import CreateVectorSnapshotInput
from modules.agent.application.use_cases.materialize_development_vector import MaterializeDevelopmentVector
from modules.agent.application.use_cases.vector_snapshot_use_cases import _normalize_build_config
from modules.agent.domain.vector_snapshot_entities import VectorSnapshot
from shared.contracts.errors import ConflictError


def setup_case(status="READY"):
    request = CreateVectorSnapshotInput(
        project_id=uuid4(), collection_id=uuid4(), version="a" * 64,
        embedding_provider_model_id=uuid4(), document_ids=[uuid4()],
    )
    snapshot = VectorSnapshot(
        project_id=request.project_id, collection_id=request.collection_id,
        version=request.version, embedding_provider_model_id=request.embedding_provider_model_id,
        embedding_provider="custom", embedding_model="embed", status=status,
        build_config=_normalize_build_config(request, embedding={"dimensions": 1536}),
    )
    repository = AsyncMock()
    repository.get_by_collection_version.return_value = snapshot
    repository.list_snapshot_documents.return_value = [SimpleNamespace(document_id=request.document_ids[0])]
    create = AsyncMock()
    return request, snapshot, repository, create


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["READY", "BUILDING"])
async def test_exact_snapshot_reuses_native_identity_without_rebuild(status):
    request, snapshot, repository, create = setup_case(status)
    result = await MaterializeDevelopmentVector(repository, create).execute(request)
    assert result.id == snapshot.id
    create.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_build_gets_a_new_immutable_retry_version():
    request, snapshot, repository, create = setup_case("FAILED")
    repository.get_by_collection_version.side_effect = [snapshot, None]
    await MaterializeDevelopmentVector(repository, create).execute(request)
    retried = create.execute.await_args.args[0]
    assert retried.version == request.version[:52] + "-retry-1"
    assert retried.document_ids == request.document_ids
    assert snapshot.status == "FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["documents", "embedding", "config", "archived"])
async def test_existing_version_with_different_evidence_is_never_reused(change):
    request, snapshot, repository, create = setup_case()
    if change == "documents":
        repository.list_snapshot_documents.return_value = [SimpleNamespace(document_id=uuid4())]
    elif change == "embedding":
        snapshot.embedding_provider_model_id = uuid4()
    elif change == "config":
        snapshot.build_config["chunking"]["chunk_size"] = 1000
    else:
        snapshot.status = "ARCHIVED"
    with pytest.raises(ConflictError):
        await MaterializeDevelopmentVector(repository, create).execute(request)
    create.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_freezes_only_selected_documents_in_a_shared_collection():
    from modules.agent.application.use_cases.vector_snapshot_use_cases import CreateVectorSnapshotUseCase

    request, _, _, _ = setup_case()
    selected = SimpleNamespace(id=request.document_ids[0], status="READY", title="Declared", file_name="policy.txt", parser="text")
    unrelated = SimpleNamespace(id=uuid4(), status="READY", title="Other", file_name="other.txt", parser="text")
    snapshots = AsyncMock()
    snapshots.get_active_building_by_collection.return_value = None
    snapshots.get_by_collection_version.return_value = None
    snapshots.list_by_collection.return_value = []
    snapshots.create.side_effect = lambda snapshot: snapshot
    collections = AsyncMock()
    collections.get_by_id.return_value = SimpleNamespace(project_id=request.project_id)
    documents = AsyncMock()
    documents.list_by_collection.return_value = [selected, unrelated]
    models = AsyncMock()
    credential_id = uuid4()
    models.get_by_id.return_value = SimpleNamespace(id=request.embedding_provider_model_id, project_id=request.project_id, status="active", metadata={"capability": "embedding"}, model="fake-embedding", provider_credential_id=credential_id)
    credentials = AsyncMock()
    credentials.get_by_id.return_value = SimpleNamespace(project_id=request.project_id, status="active", provider="custom")
    use_case = CreateVectorSnapshotUseCase(snapshot_repo=snapshots, collection_repo=collections, document_repo=documents, provider_model_repo=models, credential_repo=credentials)
    result = await use_case.execute(request)
    assert result.document_count == 1
    assert [item.document_id for item in snapshots.add_snapshot_documents.await_args.args[0]] == [selected.id]
    with pytest.raises(ConflictError):
        await use_case.execute(request.model_copy(update={"document_ids": [selected.id, selected.id]}))
