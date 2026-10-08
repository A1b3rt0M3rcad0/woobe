"""Owner stage CAS/receipt and native acceptance share one SQL transaction."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.agent.infra.database import models as agent_native
from modules.agent.infra.database import asac_models as agent
from modules.network.infra.database import models as network_native
from modules.network.infra.database import asac_models as network
from modules.package.infra.models import PackageOperationModel
from shared.contracts.asac import asac_digest
from shared.contracts.asac_requests import OpenASaCDraft, RegisterASaCRevision, SaveASaCDraft, StageASaCRevision
from shared.contracts.errors import ConflictError
from shared.infra.asac_candidate_store import ASaCCandidateStore
from shared.infra.asac_draft_store import ASaCDraftStore
from shared.security.principal import AuthenticatedPrincipal


@pytest.fixture(params=[("Agent", agent), ("Network", network)])
async def candidate_fixture(request):
    kind, tables = request.param
    engine = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"agent": None, "network": None, "package": None}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        for table in [tables.ASaCResourceModel, tables.ASaCDraftModel, tables.ASaCRevisionModel, tables.ASaCOperationModel, tables.ASaCCandidateModel, PackageOperationModel]:
            await conn.run_sync(table.__table__.create)
    project, root, uid, artifact_id = [uuid4() for _ in range(4)]
    artifact = {"artifact_id": str(artifact_id), "artifact_digest": "sha256:" + "a" * 64,
        "definition_digest": "sha256:" + "b" * 64, "kind": kind, "resource_id": str(root),
        "component_digests": {"root": "sha256:" + "c" * 64}, "provider_digests": {},
        "manifest": {"spec": {"entrypoint": {"kind": kind, "ref": "root"}}},
        "source": {"environment": "production", "snapshot_id": str(uuid4())}}
    owner = SimpleNamespace(inspect=AsyncMock(return_value={"revision": 12}))
    artifacts = SimpleNamespace(retain_export=AsyncMock(return_value=artifact), retain_upload=AsyncMock(return_value=artifact), get=AsyncMock(return_value=artifact))
    drafts = ASaCDraftStore(transactions=sessions, kind=kind, owner=owner, drafts=tables.ASaCDraftModel, revisions=tables.ASaCRevisionModel, operations=tables.ASaCOperationModel, identities=tables.ASaCResourceModel, artifacts=artifacts)
    principal = AuthenticatedPrincipal(user_id=uuid4(), session_id=uuid4(), issued_at=datetime.now(UTC), expires_at=datetime.now(UTC) + timedelta(hours=1))
    args = dict(project_id=project, resource_id=root, principal=principal)
    opened = await drafts.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="hotfix", source_export_id=uuid4()))
    record = dict(format="woobe-revision", schema_version="1.0", revision_id="rv_" + str(uuid4()), resource_uid=str(uid), kind=kind, parents=[], message="Historical correction", artifact_digest=artifact["artifact_digest"], definition_digest=artifact["definition_digest"], definition_digest_scope="woobe-portable-definition@1.0", component_digests={str(uid): artifact["component_digests"]["root"]})
    record["record_digest"] = asac_digest("record", record)
    await drafts.register_revision(**args, request=RegisterASaCRevision(operation_id=uuid4(), draft_id=opened["draft_id"], expected_generation=1, record=record, component_uids={"root": uid}))
    proposal = {"candidate_id": str(uuid4()), "snapshot_ids": {str(uid): str(uuid4())}}

    async def accept(*, session, **kwargs):
        row = PackageOperationModel(project_id=project, actor="authorized", key_digest=b"key", payload_fingerprint=b"digest", payload_ciphertext="protected", principal_ciphertext="protected", artifact_digest="a" * 64, upload_id=uuid4(), plan_id=uuid4(), lifecycle="staging", state="accepted", phases_total=1)
        session.add(row)
        await session.flush()
        return {"operation_id": str(row.id)}

    preparation = SimpleNamespace(prepare=AsyncMock(return_value=proposal), accept=AsyncMock(side_effect=accept))
    store = ASaCCandidateStore(drafts=drafts, candidates=tables.ASaCCandidateModel, preparation=preparation)
    stage = StageASaCRevision(operation_id=uuid4(), draft_id=opened["draft_id"], expected_generation=1, revision_id=record["revision_id"], registry_id=uuid4())
    yield store, drafts, sessions, tables, args, stage
    await engine.dispose()


@pytest.mark.asyncio
async def test_stage_is_exact_accepted_preparation_not_publication_or_ready(candidate_fixture):
    store, drafts, sessions, tables, args, request = candidate_fixture
    result = await store.stage(**args, request=request, api_origin="https://woobe.invalid")
    assert result["state"] == "preparing" and not result["complete"] and not result["published"]
    assert result["snapshot_id"] is None and result["runtime_digest"] is None and not result["production_changed"]
    assert result["revision_id"] == request.revision_id and result["write_outcome"] == "committed"
    assert await store.stage(**args, request=request, api_origin="https://woobe.invalid") == result
    assert store.preparation.prepare.await_count == store.preparation.accept.await_count == 1
    with pytest.raises(ConflictError, match="OPERATION_CONFLICT"):
        await store.stage(**args, request=request.model_copy(update={"registry_id": uuid4()}), api_origin="https://woobe.invalid")
    source = await drafts.get_draft(**args, draft_id=request.draft_id)
    assert source["generation"] == 1 and source["working_revision_id"] == request.revision_id
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PackageOperationModel)) == 1
        assert await session.scalar(select(func.count()).select_from(tables.ASaCCandidateModel)) == 1


@pytest.mark.asyncio
async def test_draft_race_during_semantic_inspection_does_not_accept_native_operation(candidate_fixture):
    store, drafts, sessions, tables, args, request = candidate_fixture
    proposal = store.preparation.prepare.return_value

    async def racing(**kwargs):
        await drafts.save_draft(**args, draft_id=request.draft_id, request=SaveASaCDraft(operation_id=uuid4(), expected_generation=1, upload_id=uuid4(), artifact_digest="sha256:" + "a" * 64))
        return proposal

    store.preparation.prepare.side_effect = racing
    with pytest.raises(ConflictError, match="DRAFT_CHANGED"):
        await store.stage(**args, request=request, api_origin="https://woobe.invalid")
    assert store.preparation.accept.await_count == 0
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PackageOperationModel)) == 0
        assert await session.scalar(select(func.count()).select_from(tables.ASaCCandidateModel)) == 0


@pytest.mark.asyncio
async def test_owner_failure_rolls_back_candidate_and_native_acceptance(candidate_fixture, monkeypatch):
    store, drafts, sessions, tables, args, request = candidate_fixture

    def failure(*args, **kwargs):
        raise ConflictError("injected owner failure")

    monkeypatch.setattr(drafts, "_receipt", failure)
    with pytest.raises(ConflictError, match="owner failure"):
        await store.stage(**args, request=request, api_origin="https://woobe.invalid")
    assert store.preparation.accept.await_count == 1
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(PackageOperationModel)) == 0
        assert await session.scalar(select(func.count()).select_from(tables.ASaCCandidateModel)) == 0
