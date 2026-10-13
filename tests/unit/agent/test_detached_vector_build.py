from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.database import detached_vector_build as module
from shared.contracts.errors import ConflictError


@pytest.mark.asyncio
@pytest.mark.parametrize("conflict", [None, "worker", "document"])
async def test_vector_results_commit_together_with_short_transactions_and_ownership(monkeypatch, conflict):
    active = 0
    vector_id, document_id = uuid4(), uuid4()
    original = SimpleNamespace(id=document_id, sha256="hash", storage_key="safe-path", updated_at=datetime.now(UTC))
    row = deepcopy(original)
    owner = SimpleNamespace(id=vector_id, status="BUILDING", locked_by="worker-a")
    class Uow:
        def __init__(self): self.session = SimpleNamespace(scalar=AsyncMock(return_value=owner), get=AsyncMock(return_value=row))
        def mark_read_only(self): return self
        async def __aenter__(self):
            nonlocal active
            active += 1
            assert active == 1
            return self
        async def __aexit__(self, *args):
            nonlocal active
            active -= 1
    documents = AsyncMock()
    documents.get_by_id.return_value = deepcopy(original)
    snapshots = AsyncMock()
    async def writing(*args, **kwargs):
        assert active == 1
        return SimpleNamespace(status="READY")
    for name in ("update_snapshot_document_chunk_count", "delete_snapshot_chunks", "add_snapshot_chunks", "mark_ready"):
        getattr(snapshots, name).side_effect = writing
    documents.update.side_effect = writing
    monkeypatch.setattr(module, "SQLAlchemyDocumentRepository", lambda uow: documents)
    monkeypatch.setattr(module, "SQLAlchemyVectorSnapshotRepository", lambda uow: snapshots)
    staged_documents = module._StagedDocuments(Uow)
    staged_snapshots = module._StagedSnapshots(Uow, "worker-a", staged_documents)
    document = await staged_documents.get_by_id(document_id)
    assert active == 0
    # External parsing/embedding happens here with no open owner transaction.
    document.indexed_at = datetime.now(UTC)
    await staged_documents.update(document)
    await staged_snapshots.delete_snapshot_chunks(vector_id)
    await staged_snapshots.add_snapshot_chunks([SimpleNamespace(vector_snapshot_id=vector_id)])
    await staged_snapshots.update_snapshot_document_chunk_count(vector_id, document_id, 1)
    documents.update.assert_not_awaited()
    snapshots.add_snapshot_chunks.assert_not_awaited()
    assert active == 0
    if conflict == "worker": owner.locked_by = "worker-b"
    if conflict == "document": row.sha256 = "changed"
    if conflict:
        with pytest.raises(ConflictError):
            await staged_snapshots.mark_ready(vector_id, snapshot_hash="result", document_count=1, chunk_count=1)
        documents.update.assert_not_awaited()
        snapshots.mark_ready.assert_not_awaited()
        snapshots.add_snapshot_chunks.assert_not_awaited()
    else:
        result = await staged_snapshots.mark_ready(vector_id, snapshot_hash="result", document_count=1, chunk_count=1)
        assert result.status == "READY"
        documents.update.assert_awaited_once()
        snapshots.delete_snapshot_chunks.assert_awaited_once_with(vector_id)
        snapshots.add_snapshot_chunks.assert_awaited_once()
        snapshots.mark_ready.assert_awaited_once()
    assert active == 0


@pytest.mark.asyncio
async def test_vector_credential_pins_once_and_resolves_only_at_transport_without_sql(monkeypatch):
    active = 0
    class Uow:
        session = object()
        def __init__(self, engine): pass
        async def __aenter__(self):
            nonlocal active
            active += 1
            return self
        async def __aexit__(self, *args):
            nonlocal active
            active -= 1
    monkeypatch.setattr(module, "AgentUnitOfWork", Uow)
    async def acquire(**kwargs):
        assert active == 1
        assert kwargs["environment"] == "staging"
    port = SimpleNamespace(acquire=AsyncMock(side_effect=acquire))
    monkeypatch.setattr(module, "configuration_for_session", lambda session: port)
    async def resolve(**kwargs):
        assert active == 0
        assert kwargs["field_path"] == "/authentication/fields/api_key"
        return "PRIVATE-CANARY"
    resolver = AsyncMock(side_effect=resolve)
    monkeypatch.setattr(module, "resolve_runtime_configuration", resolver)
    project = uuid4()
    snapshot = SimpleNamespace(id=uuid4(), project_id=project, build_config={}, preparation_environment="staging", embedding_provider="openai", embedding_model="embedding")
    model = SimpleNamespace(project_id=project, metadata={}, model="embedding", provider_credential_id=uuid4())
    credential = SimpleNamespace(id=uuid4(), project_id=project, status="active", provider="openai", binding_revision=1, metadata={},
        authentication={"type":"api_key", "fields":{"api_key":{"source":"project_environment", "key":"EMBEDDING_KEY"}}})
    build = module.DetachedVectorBuild(engine=None, worker_id="worker", storage=None, embedding_factory=None, encryption_key="unused", use_case_factory=None)
    bound = await build._credential(snapshot, model, credential)
    assert active == 0
    port.acquire.assert_awaited_once()
    resolver.assert_not_awaited()
    for _ in range(2):
        assert await bound.resolve("https://api.openai.com/v1/embeddings") == "PRIVATE-CANARY"
    assert resolver.await_count == 2
    assert "PRIVATE-CANARY" not in repr(bound)


def test_vector_definition_pins_model_and_connection_revisions_without_values():
    from modules.agent.domain.vector_configuration import vector_configuration_identity, verify_vector_configuration
    model = SimpleNamespace(provider_credential_id=uuid4(), model="embedding", updated_at=datetime.now(UTC))
    credential = SimpleNamespace(provider="openai", binding_revision=1)
    evidence = vector_configuration_identity(model, credential)
    snapshot = SimpleNamespace(embedding_provider="openai", embedding_model="embedding", build_config={"embedding": evidence})
    verify_vector_configuration(snapshot, model, credential)
    for field, value in [("binding_revision", 2), ("provider", "custom")]:
        changed = deepcopy(credential)
        setattr(changed, field, value)
        with pytest.raises(ConflictError):
            verify_vector_configuration(snapshot, model, changed)
    changed = deepcopy(model)
    changed.provider_credential_id = uuid4()
    with pytest.raises(ConflictError):
        verify_vector_configuration(snapshot, changed, credential)
    assert set(evidence) == {"provider_credential_id", "credential_binding_revision", "provider_model_revision"}
