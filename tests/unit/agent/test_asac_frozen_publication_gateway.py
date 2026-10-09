from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select, func

from tests.unit.agent.test_asac_draft_store import drafts
from modules.agent.infra.database.asac_models import ASaCOperationModel
from modules.agent.infra.database.frozen_publication_gateway import AgentFrozenPublicationGateway
from shared.contracts.asac_constituent_publication import PublishFrozenConstituent
from shared.contracts.errors import AuthorizationError, ConflictError


def constituent_request():
    return PublishFrozenConstituent(operation_id=uuid4(), parent_operation_id=uuid4(),
        parent_resource_id=uuid4(), parent_candidate_id=uuid4(), parent_evaluation_id=uuid4(),
        snapshot_id=uuid4(), expected_runtime_digest="sha256:" + "d" * 64,
        reason="Publish exact Network constituent")


def gateway(store, request):
    publisher = SimpleNamespace(publish=AsyncMock(return_value={"release_id": uuid4(),
        "release_version": "v0.0.20261009.01", "runtime_digest": request.expected_runtime_digest,
        "reused": False}))
    snapshots = SimpleNamespace(read=AsyncMock(return_value={"runtime_digest": request.expected_runtime_digest,
        "runtime_snapshot": {"provider": "custom", "model": "exact"}, "release_status": "released"}))
    return AgentFrozenPublicationGateway(drafts=store, publisher=publisher, snapshots=snapshots)


@pytest.mark.asyncio
async def test_frozen_constituent_replays_original_owner_receipt_and_parent_identity(drafts):
    store, sessions, args, uid, artifact = drafts
    request = constituent_request()
    service = gateway(store, request)
    receipt = await service.publish(**args, request=request)
    assert receipt["parent_candidate_id"] == str(request.parent_candidate_id)
    assert receipt["source_snapshot_id"] == str(request.snapshot_id)
    assert not receipt["production_changed"] and receipt["complete"]
    assert await service.publish(**args, request=request) == receipt
    assert service.publisher.publish.await_count == 1
    authority = store.owner.inspect.await_args.kwargs
    assert authority["lock"] and authority["required_permission"] == "agent:version"
    assert authority["environment"] == "staging"
    with pytest.raises(ConflictError, match="OPERATION_CONFLICT"):
        await service.publish(**args, request=request.model_copy(update={"parent_candidate_id": uuid4()}))
    with pytest.raises(ConflictError, match="OPERATION_CONFLICT"):
        await service.publish(**args, request=request.model_copy(update={"snapshot_id": uuid4()}))
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ASaCOperationModel)) == 1


@pytest.mark.asyncio
async def test_frozen_constituent_failure_rolls_back_original_operation(drafts):
    store, sessions, args, uid, artifact = drafts
    request = constituent_request()
    service = gateway(store, request)
    service.publisher.publish.return_value["runtime_digest"] = "wrong"
    with pytest.raises(ConflictError, match="RUNTIME_CHANGED"):
        await service.publish(**args, request=request)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ASaCOperationModel)) == 0
    service.publisher.publish.return_value["runtime_digest"] = request.expected_runtime_digest
    assert (await service.publish(**args, request=request))["complete"]


@pytest.mark.asyncio
async def test_frozen_constituent_rechecks_authority_even_for_replay(drafts):
    store, sessions, args, uid, artifact = drafts
    request = constituent_request()
    service = gateway(store, request)
    await service.publish(**args, request=request)
    store.owner.inspect.side_effect = AuthorizationError("Revoked")
    with pytest.raises(AuthorizationError):
        await service.publish(**args, request=request)
    assert service.publisher.publish.await_count == 1


@pytest.mark.asyncio
async def test_frozen_constituent_read_and_stored_projection_must_match(drafts):
    store, sessions, args, uid, artifact = drafts
    request = constituent_request()
    service = gateway(store, request)
    inspected = await service.inspect(**args, snapshot_id=request.snapshot_id)
    assert inspected["runtime_digest"] == request.expected_runtime_digest
    assert store.owner.inspect.await_args.kwargs["required_permission"] == "agent:read"
    service.snapshots.read.return_value["runtime_digest"] = "wrong"
    with pytest.raises(ConflictError, match="stored constituent differs"):
        await service.publish(**args, request=request)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ASaCOperationModel)) == 0
