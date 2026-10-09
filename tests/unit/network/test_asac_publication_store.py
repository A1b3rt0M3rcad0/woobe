from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func

from tests.unit.agent.test_asac_evaluation_store import evaluation_fixture
from tests.unit.agent.test_asac_candidate_store import candidate_fixture
from modules.network.infra.database import asac_models as network
from modules.network.infra.services.asac_publication_store import NetworkASaCPublicationStore
from shared.contracts.asac_publication import PublishASaCCandidate
from shared.contracts.errors import ConflictError

pytestmark = [pytest.mark.asyncio,
    pytest.mark.parametrize("candidate_fixture", [("Network", network)], indirect=True)]


@pytest.fixture
async def publication(evaluation_fixture):
    evaluations, args, candidate_id, request, runs, tables, sessions = evaluation_fixture
    async with sessions.begin() as session:
        for model in (network.ASaCPublicationModel, network.ASaCPublicationPreparationModel, network.ASaCConstituentPublicationModel):
            await session.run_sync(lambda sync, model=model: model.__table__.create(sync.connection()))
    accepted, _ = await evaluations.accept(**args, candidate_id=candidate_id, request=request)
    await evaluations.execute(**args, evaluation_id=UUID(accepted["evaluation_id"]))
    async with sessions() as session:
        candidate_record = await session.get(tables.ASaCCandidateModel, candidate_id)
        record_digest = candidate_record.record_digest
    source = {"record_digest": record_digest, "runtime_digest": "sha256:" + "d" * 64, "runtime_digest_scope": "network-execution-runtime@2", "bindings": {}}
    for _ in range(2):
        node = str(uuid4())
        source["bindings"][node] = {"agent_id": str(uuid4()), "release_id": str(uuid4()), "runtime_digest": "sha256:" + "e" * 64}
    receipts, copies = {}, []
    fail_node = [None]

    async def copy(**kwargs):
        child = kwargs["request"]
        if str(kwargs["resource_id"]) == fail_node[0]:
            raise ConflictError("ASAC_TEST_PHASE_FAILED: controlled interruption")
        if child.operation_id not in receipts:
            receipts[child.operation_id] = {"project_id": str(args["project_id"]),
                "resource_id": str(kwargs["resource_id"]), "source_snapshot_id": str(child.snapshot_id),
                "release_id": str(uuid4()), "runtime_digest": child.expected_runtime_digest,
                "release_version": "v0.0.20261009.01", "complete": True}
            copies.append(child.operation_id)
        return receipts[child.operation_id]

    gateway = N(inspect=AsyncMock(return_value={"runtime_digest": "sha256:" + "e" * 64}), publish=AsyncMock(side_effect=copy))
    native = N(capture=AsyncMock(return_value=source), publish=AsyncMock(return_value={
        "release_id": uuid4(), "release_version": "v0.0.20261009.01", "reused": False, "runtime_digest": source["runtime_digest"]}))
    store = NetworkASaCPublicationStore(evaluations=evaluations, publications=network.ASaCPublicationModel,
        publisher=native, constituents=gateway)
    publish = PublishASaCCandidate(operation_id=uuid4(), candidate_id=candidate_id,
        evaluation_id=UUID(accepted["evaluation_id"]), reason="Qualified Network closure")
    yield store, args, publish, sessions, source, fail_node, copies


async def test_partial_publication_recovers_original_phases_without_second_root(publication):
    store, args, request, sessions, source, fail_node, copies = publication
    keys = sorted(source["bindings"])
    fail_node[0] = source["bindings"][keys[1]]["agent_id"]
    accepted = await store.publish(**args, request=request)
    assert accepted["state"] == "preparing" and not accepted["complete"] and not accepted["published"]
    identifier = UUID(accepted["publication_id"])
    partial = await store.get(**args, publication_id=identifier)
    assert partial["prepared_constituents"] == 1 and partial["required_constituents"] == 2
    assert partial["error_code"] == "ASAC_TEST_PHASE_FAILED"
    store.publisher.publish.assert_not_awaited()
    assert await store.publish(**args, request=request) == accepted
    assert len(copies) == 1
    fail_node[0] = None
    published = await store.reconcile(**args, publication_id=identifier)
    assert published["published"] and not published["production_changed"] and len(copies) == 2
    assert published["runtime_digest"] == source["runtime_digest"]
    assert len(published["constituent_releases"]) == 2
    assert await store.reconcile(**args, publication_id=identifier) == published
    assert await store.publish(**args, request=request) == accepted
    assert store.publisher.publish.await_count == 1
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(network.ASaCPublicationModel)) == 1
        assert await session.scalar(select(func.count()).select_from(network.ASaCConstituentPublicationModel)) == 2


async def test_publication_scope_payload_and_actor_cannot_replace_original_intent(publication):
    store, args, request, sessions, source, fail_node, copies = publication
    fail_node[0] = source["bindings"][sorted(source["bindings"])[0]]["agent_id"]
    accepted = await store.publish(**args, request=request)
    with pytest.raises(ConflictError, match="OPERATION_CONFLICT"):
        await store.publish(**args, request=request.model_copy(update={"reason": "Changed original reason"}))
    other = args["principal"].model_copy(update={"user_id": uuid4()})
    with pytest.raises(ConflictError, match="ACTOR_MISMATCH"):
        await store.reconcile(**{**args, "principal": other}, publication_id=UUID(accepted["publication_id"]))
    store.publisher.publish.assert_not_awaited()


async def test_native_root_mismatch_preserves_prepared_identity_without_publication(publication):
    store, args, request, sessions, source, fail_node, copies = publication
    store.publisher.publish.return_value["runtime_digest"] = "changed"
    accepted = await store.publish(**args, request=request)
    assert accepted["state"] == "preparing"
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(network.ASaCPublicationModel)) == 0
        assert await session.scalar(select(func.count()).select_from(network.ASaCConstituentPublicationModel)) == 0
    assert len(copies) == 2
    store.publisher.publish.return_value["runtime_digest"] = source["runtime_digest"]
    assert (await store.reconcile(**args, publication_id=UUID(accepted["publication_id"])))["published"]
    assert len(copies) == 2


async def test_cancel_partial_preparation_keeps_copies_but_never_publishes_root(publication):
    from shared.contracts.asac_publication import CancelASaCPublication
    store, args, request, sessions, source, fail_node, copies = publication
    fail_node[0] = source["bindings"][sorted(source["bindings"])[1]]["agent_id"]
    accepted = await store.publish(**args, request=request)
    identifier = UUID(accepted["publication_id"])
    cancellation = CancelASaCPublication(reason="Discard blocked qualification")
    closed = await store.cancel(**args, publication_id=identifier, request=cancellation)
    assert closed["state"] == "cancelled" and closed["complete"] and not closed["published"]
    assert not closed["production_changed"] and len(copies) == 1
    assert await store.cancel(**args, publication_id=identifier, request=cancellation) == closed
    assert await store.get(**args, publication_id=identifier) == closed
    fail_node[0] = None
    with pytest.raises(ConflictError, match="PUBLICATION_CANCELLED"):
        await store.reconcile(**args, publication_id=identifier)
    assert len(copies) == 1
    store.publisher.publish.assert_not_awaited()


async def test_committed_publication_cannot_be_cancelled(publication):
    from shared.contracts.asac_publication import CancelASaCPublication
    store, args, request, sessions, source, fail_node, copies = publication
    published = await store.publish(**args, request=request)
    with pytest.raises(ConflictError, match="ALREADY_COMMITTED"):
        await store.cancel(**args, publication_id=UUID(published["publication_id"]),
            request=CancelASaCPublication(reason="Cannot undo publication"))
