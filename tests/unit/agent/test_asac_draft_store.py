"""Owner record mechanics exercised against transactional SQL persistence."""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.agent.infra.database.models import AgentModel  # register native FK target
from modules.agent.infra.database.asac_models import ASaCDraftModel, ASaCRevisionModel, ASaCOperationModel, ASaCResourceModel
from shared.contracts.asac import asac_digest
from shared.contracts.asac_requests import OpenASaCDraft, SaveASaCDraft, RegisterASaCRevision
from shared.contracts.errors import ConflictError, AuthorizationError
from shared.infra.asac_draft_store import ASaCDraftStore
from shared.security.principal import AuthenticatedPrincipal


@pytest.fixture
async def drafts():
    engine = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map":{"agent":None}})
    tables = [ASaCResourceModel.__table__, ASaCDraftModel.__table__, ASaCRevisionModel.__table__, ASaCOperationModel.__table__]
    async with engine.begin() as connection:
        for table in tables:
            await connection.run_sync(table.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    project, resource, uid, artifact_id = uuid4(), uuid4(), uuid4(), uuid4()
    owner = SimpleNamespace(inspect=AsyncMock(return_value={"revision":4}))
    artifact = {"artifact_id":str(artifact_id), "artifact_digest":"sha256:"+"a"*64,
        "definition_digest":"sha256:"+"b"*64, "kind":"Agent", "resource_id":str(resource),
        "component_digests":{"root":"sha256:"+"c"*64}, "provider_digests":{},
        "manifest":{"spec":{"entrypoint":{"kind":"Agent","ref":"root"}}},
        "source":{"kind":"release","environment":"production","snapshot_id":str(uuid4())}}
    artifacts = SimpleNamespace(retain_export=AsyncMock(return_value=artifact), retain_upload=AsyncMock(return_value=artifact), get=AsyncMock(return_value=artifact))
    store = ASaCDraftStore(transactions=sessions, kind="Agent", owner=owner,
        drafts=ASaCDraftModel, revisions=ASaCRevisionModel, operations=ASaCOperationModel,
        identities=ASaCResourceModel, artifacts=artifacts)
    principal = AuthenticatedPrincipal(user_id=uuid4(), session_id=uuid4(), issued_at=datetime.now(UTC), expires_at=datetime.now(UTC)+timedelta(hours=1))
    args = dict(project_id=project, resource_id=resource, principal=principal)
    yield store, sessions, args, uid, artifact
    await engine.dispose()


@pytest.mark.asyncio
async def test_drafts_coexist_preserve_default_and_replay_without_export(drafts):
    store, sessions, args, uid, artifact = drafts
    first_request = OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="hotfix", source_export_id=uuid4())
    hotfix = await store.open_draft(**args, request=first_request)
    second = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="feature", source_export_id=uuid4()))
    assert hotfix["draft_id"] != second["draft_id"] and not hotfix["production_changed"]
    listed = await store.list_drafts(**args)
    assert {item["name"] for item in listed["drafts"]} == {"default","hotfix","feature"}
    default = next(item for item in listed["drafts"] if item["name"] == "default")
    assert default["artifact_id"] is None and default["origin"]["origin_status"] == "unknown_origin"
    calls = store.artifacts.retain_export.await_count
    assert await store.open_draft(**args, request=first_request) == hotfix
    assert store.artifacts.retain_export.await_count == calls
    with pytest.raises(ConflictError, match="ASAC_OPERATION_CONFLICT"):
        await store.open_draft(**args, request=first_request.model_copy(update={"name":"other"}))
    other_resource = uuid4()
    artifact["resource_id"] = str(other_resource)
    with pytest.raises(ConflictError, match="ASAC_IDENTITY_CONFLICT"):
        await store.open_draft(**{**args,"resource_id":other_resource}, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="different", source_export_id=uuid4()))


@pytest.mark.asyncio
async def test_generation_cas_and_operation_reconciliation(drafts):
    store, sessions, args, uid, artifact = drafts
    draft = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="default", source_export_id=uuid4()))
    from uuid import UUID
    draft_id = UUID(draft["draft_id"])
    save = SaveASaCDraft(operation_id=uuid4(), expected_generation=1, upload_id=uuid4(), artifact_digest=artifact["artifact_digest"])
    saved = await store.save_draft(**args, draft_id=draft_id, request=save)
    assert saved["generation"] == 2
    assert await store.save_draft(**args, draft_id=draft_id, request=save) == saved
    receipt = await store.operation(**args, operation_id=save.operation_id)
    assert receipt["state"] == "committed" and receipt["result"] == saved
    with pytest.raises(ConflictError, match="ASAC_DRAFT_CHANGED"):
        await store.save_draft(**args, draft_id=draft_id, request=save.model_copy(update={"operation_id":uuid4()}))
    assert (await store.get_draft(**args, draft_id=draft_id))["generation"] == 2
    async with sessions.begin() as session:
        assert await session.scalar(select(func.count()).select_from(ASaCOperationModel)) == 2
    unknown = await store.operation(**args, operation_id=uuid4())
    assert not unknown["complete"] and not unknown["retry_authorized"]


@pytest.mark.asyncio
async def test_registration_verifies_closed_object_and_immutable_lineage(drafts):
    store, sessions, args, uid, artifact = drafts
    draft = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="default", source_export_id=uuid4()))
    record = dict(format="woobe-revision",schema_version="1.0",revision_id="rv_"+str(uuid4()),resource_uid=str(uid),kind="Agent",parents=[],message="Checkpoint",artifact_digest=artifact["artifact_digest"],definition_digest=artifact["definition_digest"],definition_digest_scope="woobe-portable-definition@1.0",component_digests={str(uid):artifact["component_digests"]["root"]})
    record["record_digest"] = asac_digest("record",record)
    request = RegisterASaCRevision(operation_id=uuid4(), draft_id=draft["draft_id"], expected_generation=1, record=record, component_uids={"root":uid})
    receipt = await store.register_revision(**args,request=request)
    assert receipt["record"] == record and not receipt["production_changed"]
    forged = {**record,"definition_digest":"sha256:"+"d"*64}
    forged.pop("record_digest");forged["record_digest"] = asac_digest("record",forged)
    with pytest.raises(ConflictError, match="ASAC_REVISION_MISMATCH"):
        await store.register_revision(**args,request=RegisterASaCRevision(**{**request.model_dump(),"operation_id":uuid4(),"record":forged}))
    changed = {**record,"message":"Other bytes"}
    changed.pop("record_digest");changed["record_digest"] = asac_digest("record",changed)
    with pytest.raises(ConflictError, match="ASAC_INTEGRITY_CONFLICT"):
        await store.register_revision(**args,request=RegisterASaCRevision(**{**request.model_dump(),"operation_id":uuid4(),"record":changed}))
    store.owner.inspect.side_effect = AuthorizationError("revoked")
    with pytest.raises(AuthorizationError):
        await store.register_revision(**args,request=request)


@pytest.mark.asyncio
async def test_author_digest_is_explicitly_declared_not_verified(drafts):
    store, sessions, args, uid, artifact = drafts
    draft = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="source", source_export_id=uuid4()))
    record = dict(format="woobe-revision", schema_version="1.0", revision_id="rv_"+str(uuid4()), resource_uid=str(uid), kind="Agent", parents=[], message="Source checkpoint", artifact_digest=artifact["artifact_digest"], author_artifact_digest="sha256:"+"f"*64, definition_digest=artifact["definition_digest"], definition_digest_scope="woobe-portable-definition@1.0", component_digests={str(uid): artifact["component_digests"]["root"]})
    record["record_digest"] = asac_digest("record", record)
    request = RegisterASaCRevision(operation_id=uuid4(), draft_id=draft["draft_id"], expected_generation=1, record=record, component_uids={"root":uid})
    result = await store.register_revision(**args, request=request)
    assert result["record"] == record
    assert result["author_artifact_status"] == "declared_not_retained"
    fetched = await store.get_revision(**args, revision_id=record["revision_id"])
    assert fetched["author_artifact_status"] == "declared_not_retained"
    assert fetched["record"] == record


@pytest.mark.asyncio
async def test_revision_catalog_watermark_scope_and_revoked_authority(drafts):
    from shared.contracts.errors import ValidationError
    store, sessions, args, uid, artifact = drafts
    store.cursor_key = "test-cursor-key"
    draft = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="catalog", source_export_id=uuid4()))
    records = []

    async def checkpoint():
        record = dict(format="woobe-revision", schema_version="1.0", revision_id="rv_" + str(uuid4()), resource_uid=str(uid), kind="Agent", parents=[records[-1]["revision_id"]] if records else [], message="Immutable checkpoint", artifact_digest=artifact["artifact_digest"], definition_digest=artifact["definition_digest"], definition_digest_scope="woobe-portable-definition@1.0", component_digests={str(uid): artifact["component_digests"]["root"]})
        record["record_digest"] = asac_digest("record", record)
        await store.register_revision(**args, request=RegisterASaCRevision(operation_id=uuid4(), draft_id=draft["draft_id"], expected_generation=1, record=record, component_uids={"root": uid}))
        records.append(record)

    for _ in range(3):
        await checkpoint()
    first = await store.list_revisions(**args, limit=1)
    assert first["has_more"] and not first["complete"]
    assert first["records"][0]["record"] == records[0]
    # A fourth revision inserted after page one is outside the retained watermark.
    await checkpoint()
    seen, page = [first["records"][0]["record"]], first
    while page["has_more"]:
        page = await store.list_revisions(**args, limit=1, cursor=page["next_cursor"])
        assert page["watermark"] == first["watermark"]
        seen.extend(item["record"] for item in page["records"])
    assert seen == records[:3] and page["complete"]
    assert (await store.list_revisions(**args))["records"][-1]["record"] == records[3]
    with pytest.raises(ValidationError, match="CURSOR_INVALID"):
        await store.list_revisions(**{**args, "resource_id": uuid4()}, cursor=first["next_cursor"])
    with pytest.raises(ValidationError, match="CURSOR_INVALID"):
        await store.list_revisions(**args, cursor=first["next_cursor"] + "tampered")
    with pytest.raises(ValidationError, match="REVISION_LIMIT"):
        await store.list_revisions(**args, limit=201)
    store.owner.inspect.side_effect = AuthorizationError("revoked")
    with pytest.raises(AuthorizationError):
        await store.list_revisions(**args, cursor=first["next_cursor"])


@pytest.mark.asyncio
async def test_revision_transfer_matches_closed_object_and_rechecks_authority(drafts):
    store, sessions, args, uid, artifact = drafts
    draft = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="transfer", source_export_id=uuid4()))
    record = dict(format="woobe-revision", schema_version="1.0", revision_id="rv_" + str(uuid4()), resource_uid=str(uid), kind="Agent", parents=[], message="Transfer checkpoint", artifact_digest=artifact["artifact_digest"], definition_digest=artifact["definition_digest"], definition_digest_scope="woobe-portable-definition@1.0", component_digests={str(uid): artifact["component_digests"]["root"]})
    record["record_digest"] = asac_digest("record", record)
    await store.register_revision(**args, request=RegisterASaCRevision(operation_id=uuid4(), draft_id=draft["draft_id"], expected_generation=1, record=record, component_uids={"root": uid}))
    evidence = {"artifact_digest": record["artifact_digest"], "definition_digest": record["definition_digest"], "transport_digest": "c" * 64, "size_bytes": 7, "inventory": []}
    store.artifacts.transfer = AsyncMock(return_value=(evidence, b"archive"))
    receipt, content = await store.revision_transfer(**args, revision_id=record["revision_id"])
    assert receipt["record_digest"] == record["record_digest"] and content == b"archive"
    assert receipt["author_artifact_status"] == "unavailable"
    store.artifacts.transfer.return_value = ({**evidence, "definition_digest": "sha256:" + "f" * 64}, b"archive")
    with pytest.raises(ConflictError, match="executable object differs"):
        await store.revision_transfer(**args, revision_id=record["revision_id"])

    async def revoke_during_io(**kwargs):
        store.owner.inspect.side_effect = AuthorizationError("revoked during capture")
        return evidence, b"archive"

    store.artifacts.transfer.side_effect = revoke_during_io
    with pytest.raises(AuthorizationError, match="revoked during capture"):
        await store.revision_transfer(**args, revision_id=record["revision_id"])
    store.owner.inspect.side_effect = None
    async with sessions.begin() as session:
        row = await session.scalar(select(ASaCRevisionModel).where(ASaCRevisionModel.revision_id == record["revision_id"]))
        row.document = {**row.document, "message": "Changed without a new record digest"}
    with pytest.raises(ConflictError, match="metadata is inconsistent"):
        await store.get_revision(**args, revision_id=record["revision_id"])


@pytest.mark.asyncio
async def test_retained_author_link_keeps_record_immutable_and_rechecks_owner(drafts):
    store, sessions, args, uid, artifact = drafts
    author_id = uuid4()
    source_digest = "sha256:" + "f" * 64
    store.artifacts.authors = SimpleNamespace(retain=AsyncMock(return_value=author_id), transfer=AsyncMock(return_value=({"author_digest": source_digest, "resource_uid": str(uid), "transport_digest": "d"*64, "size_bytes": 4, "verification": "canonical_source_custody"}, b"data")))
    draft = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name="retained", source_export_id=uuid4()))
    record = dict(format="woobe-revision", schema_version="1.0", revision_id="rv_"+str(uuid4()), resource_uid=str(uid), kind="Agent", parents=[], message="Retained source", artifact_digest=artifact["artifact_digest"], author_artifact_digest=source_digest, definition_digest=artifact["definition_digest"], definition_digest_scope="woobe-portable-definition@1.0", component_digests={str(uid): artifact["component_digests"]["root"]})
    record["record_digest"] = asac_digest("record", record)
    request = RegisterASaCRevision(operation_id=uuid4(), draft_id=draft["draft_id"], expected_generation=1, record=record, component_uids={"root": uid}, author_upload_id=uuid4())
    result = await store.register_revision(**args, request=request)
    assert result["author_artifact_status"] == "retained_custody" and result["record"] == record
    calls = store.artifacts.authors.retain.await_count
    assert await store.register_revision(**args, request=request) == result
    assert store.artifacts.authors.retain.await_count == calls
    fetched = await store.get_revision(**args, revision_id=record["revision_id"])
    assert fetched["author_artifact_id"] == str(author_id)
    receipt, content = await store.author_transfer(**args, revision_id=record["revision_id"])
    assert receipt["record_digest"] == record["record_digest"] and content == b"data"
    async def revoke(**kwargs):
        store.owner.inspect.side_effect = AuthorizationError("revoked")
        return {"author_digest": source_digest, "resource_uid": str(uid)}, b"data"
    store.artifacts.authors.transfer.side_effect = revoke
    with pytest.raises(AuthorizationError):
        await store.author_transfer(**args, revision_id=record["revision_id"])


@pytest.mark.asyncio
async def test_editor_cas_replay_and_late_conflict_preserve_owner(drafts):
    from uuid import UUID
    from shared.contracts.asac_workbench import EditASaCDraft
    store, sessions, args, uid, artifact = drafts
    line = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(), resource_uid=uid, name='web', source_export_id=uuid4()))
    assert line['origin']['authoring_channel'] == 'web'
    draft_id = UUID(line['draft_id'])
    changed = {**artifact, 'artifact_id': str(uuid4()), 'definition_digest': 'sha256:'+'d'*64}
    store.artifacts.retain_edits = AsyncMock(return_value=changed)
    request = EditASaCDraft(operation_id=uuid4(), expected_generation=1, files=[{'path':'agent.yaml','content':'edited'}])
    saved = await store.edit_author_files(**args, draft_id=draft_id, request=request)
    assert saved['generation'] == 2 and saved['definition_digest'] == changed['definition_digest']
    assert saved['working_revision_id'] is None and saved['production_changed'] is False
    assert await store.edit_author_files(**args, draft_id=draft_id, request=request) == saved
    assert store.artifacts.retain_edits.await_count == 1
    with pytest.raises(ConflictError, match='ASAC_DRAFT_CHANGED'):
        await store.edit_author_files(**args, draft_id=draft_id, request=request.model_copy(update={'operation_id':uuid4()}))
    assert store.artifacts.retain_edits.await_count == 1
    async def concurrent(**kwargs):
        async with sessions.begin() as session:
            row = await session.get(ASaCDraftModel, draft_id)
            row.generation += 1
        return changed
    store.artifacts.retain_edits.side_effect = concurrent
    with pytest.raises(ConflictError, match='ASAC_DRAFT_CHANGED'):
        await store.edit_author_files(**args, draft_id=draft_id, request=request.model_copy(update={'operation_id':uuid4(),'expected_generation':2}))
    assert (await store.get_draft(**args, draft_id=draft_id))['generation'] == 3


@pytest.mark.asyncio
async def test_web_checkpoint_original_replay_and_unauthorized_editor(drafts):
    from uuid import UUID
    from shared.contracts.asac_workbench import CheckpointASaCDraft
    store, sessions, args, uid, artifact = drafts
    artifact['definition_digest_scope'] = 'woobe-portable-definition@1.0'
    artifact['provider_digests'] = {'provider':'sha256:'+'e'*64}
    line = await store.open_draft(**args, request=OpenASaCDraft(operation_id=uuid4(),resource_uid=uid,name='web',source_export_id=uuid4()))
    draft_id = UUID(line['draft_id'])
    request = CheckpointASaCDraft(operation_id=uuid4(), expected_generation=1, revision_id='rv_'+str(uuid4()),message='Web checkpoint')
    result = await store.checkpoint_editor(**args,draft_id=draft_id,request=request)
    assert result['record']['resource_uid'] == str(uid)
    assert len(result['record']['component_digests']) == 2
    assert await store.checkpoint_editor(**args,draft_id=draft_id,request=request) == result
    with pytest.raises(ConflictError, match='ASAC_OPERATION_CONFLICT'):
        await store.checkpoint_editor(**args,draft_id=draft_id,request=request.model_copy(update={'message':'other'}))
    store.artifacts.editor_source = AsyncMock(return_value={'files':[]})
    store.owner.inspect.side_effect = AuthorizationError('denied')
    with pytest.raises(AuthorizationError):
        await store.editor_source(**args,draft_id=draft_id)
    store.artifacts.editor_source.assert_not_awaited()
    with pytest.raises(AuthorizationError):
        await store.checkpoint_editor(**args,draft_id=draft_id,request=request)


@pytest.mark.asyncio
@pytest.mark.parametrize("result,environment", [
    ({"plan_id":"plan", "environment":"production"}, "production"),
    ({"plan_id":"plan", "deployment_id":"deployment", "environment":"staging"}, "staging"),
    ({"lease_id":"lease", "scope":"production"}, "production"),
    ({"lease_id":"lease", "scope":"draft:123"}, "draft"),
    ({"candidate_id":"candidate"}, "staging"),
    ({"candidate_id":"candidate", "evaluation_id":"evaluation"}, "staging"),
    ({"candidate_id":"candidate", "publication_id":"publication"}, "staging"),
    ({"draft_id":"draft", "origin":{"environment":"production"}}, "draft"),
    ({"record":{"environment":"production"}}, "draft"),
])
async def test_operation_reads_verify_persisted_environment_and_keep_actor_scope(drafts, result, environment):
    from shared.infra.admin_idempotency import principal_identity
    store, sessions, args, _, _ = drafts
    operation = uuid4()
    async with sessions.begin() as session:
        session.add(ASaCOperationModel(project_id=args["project_id"], resource_id=args["resource_id"],
            actor=principal_identity(args["principal"]), operation_id=operation,
            request_digest="sha256:" + "a" * 64, result=result))
    observed = await store.operation(**args, operation_id=operation, environment=environment)
    assert observed["result"] == result
    actual_call = store.owner.inspect.await_args.kwargs
    assert actual_call["environment"] == environment and actual_call["resource_id"] == args["resource_id"]
    if result.get("evaluation_id") and not result.get("publication_id"):
        assert actual_call["required_permission"] == "run:read"
    with pytest.raises(AuthorizationError, match="another environment"):
        await store.operation(**args, operation_id=operation, environment="draft" if environment != "draft" else "production")
    other_actor = args["principal"].model_copy(update={"user_id":uuid4()})
    hidden = await store.operation(**{**args,"principal":other_actor}, operation_id=operation, environment=environment)
    assert hidden["state"] == "not_observed" and "result" not in hidden
    assert not hidden["retry_authorized"]


@pytest.mark.asyncio
async def test_operation_default_scope_cannot_read_production_receipt_with_draft_only_grant(drafts):
    from shared.infra.admin_idempotency import principal_identity
    from shared.security.tenancy import TenantAuthorizer
    store, sessions, args, _, _ = drafts
    operation = uuid4()
    async with sessions.begin() as session:
        session.add(ASaCOperationModel(project_id=args["project_id"], resource_id=args["resource_id"],
            actor=principal_identity(args["principal"]), operation_id=operation,
            request_digest="sha256:" + "a" * 64, result={"plan_id":"plan", "environment":"production"}))
    async def constrained_owner(session, **request):
        TenantAuthorizer._require_conditions({"environments":["draft"], "target_ids":[str(args["resource_id"])]},
            permission="agent:read", path_context={"agent_id":str(request["resource_id"]),"environment":request["environment"]})
    store.owner.inspect.side_effect = constrained_owner
    with pytest.raises(AuthorizationError, match="conditions"):
        await store.operation(**args, operation_id=operation)
    with pytest.raises(AuthorizationError, match="conditions"):
        await store.operation(**args, operation_id=operation, environment="production")


@pytest.mark.asyncio
async def test_operation_read_requires_valid_environment_before_database_lookup(drafts):
    from shared.contracts.errors import ValidationError
    store, _, args, _, _ = drafts
    with pytest.raises(ValidationError, match="environment"):
        await store.operation(**args, operation_id=uuid4(), environment="other")
    store.owner.inspect.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["Agent", "Network"])
@pytest.mark.parametrize("mode", ["valid", "wrong-resource", "stale", "wrong-kind", "denied"])
async def test_source_preflight_is_read_only_and_reuses_owner_guards(drafts, kind, mode):
    store, sessions, args, uid, artifact = drafts
    store.kind = kind
    artifact["kind"] = kind
    artifact["source"] = {"kind": "draft", "draft_revision": 4}
    store.artifacts.inspect_export = AsyncMock(return_value=artifact)
    if mode == "wrong-resource":
        artifact["resource_id"] = str(uuid4())
    if mode == "wrong-kind":
        artifact["kind"] = "Network" if kind == "Agent" else "Agent"
    if mode == "stale":
        artifact["source"]["draft_revision"] = 3
    if mode == "denied":
        store.owner.inspect.side_effect = AuthorizationError("Denied")
    kwargs = dict(**args, source_export_id=uuid4(), resource_uid=uid)
    if mode == "valid":
        result = await store.preflight_draft(**kwargs)
        assert result["valid"] and not result["executed"]
        assert result["kind"] == kind and result["resource_id"] == str(args["resource_id"])
        assert result["source_export_id"] == str(kwargs["source_export_id"])
    else:
        with pytest.raises(AuthorizationError if mode == "denied" else ConflictError):
            await store.preflight_draft(**kwargs)
    assert store.artifacts.retain_export.await_count == 0
    async with sessions() as session:
        for model in [ASaCResourceModel, ASaCDraftModel, ASaCOperationModel, ASaCRevisionModel]:
            assert await session.scalar(select(func.count()).select_from(model)) == 0
