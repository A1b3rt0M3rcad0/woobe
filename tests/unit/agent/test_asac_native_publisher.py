from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from modules.agent.infra.database.asac_publisher import AgentASaCPublisher, frozen_release_entity
from modules.agent.infra.database.models import AgentReleaseModel
from modules.agent.infra.database.mappers import agent_release_model_to_entity
from modules.agent.domain.execution_definition import hash_agent_execution_snapshot
from shared.contracts.errors import ConflictError


@pytest.mark.asyncio
@pytest.mark.parametrize("reuse",[False,True])
async def test_exact_native_agent_publication_copies_or_reuses_without_selection(reuse):
    project,agent,snapshot=uuid4(),uuid4(),uuid4()
    source=AgentReleaseModel(id=snapshot,project_id=project,agent_id=agent,version=snapshot.hex,
        status="archived",snapshot_kind="candidate",session_mode="stateless",name="Exact candidate",
        provider="custom",model="model",runtime_config={"tool_bindings":[{"tool_id":"frozen"}]})
    source.provider_model_id=uuid4()
    source.fallback_provider_model_id=uuid4()
    released=deepcopy(source);released.id=uuid4();released.snapshot_kind="release";released.status="released";released.version="v0.0.20261009.01"
    session=N(get=AsyncMock(return_value=source),scalars=AsyncMock(return_value=N(all=lambda:[released] if reuse else [])),flush=AsyncMock())
    added=[];session.add=added.append
    candidate=N(root_snapshot_id=snapshot,runtime_digest="sha256:"+hash_agent_execution_snapshot(frozen_release_entity(source)))
    result=await AgentASaCPublisher().publish(session=session,project_id=project,resource_id=agent,
        candidate=candidate,principal=N(),reason="Publish exact candidate")
    assert result["runtime_digest"]==candidate.runtime_digest and result["reused"]==reuse
    assert source.snapshot_kind=="candidate" and source.status=="archived"
    assert len(added)==(0 if reuse else 1)
    if added:
        assert added[0].snapshot_kind=="release" and added[0].status=="released"
        assert added[0].runtime_config==source.runtime_config and added[0].id!=snapshot
    candidate.runtime_digest="mismatched"
    with pytest.raises(ConflictError,match="RUNTIME_CHANGED"):
        await AgentASaCPublisher().publish(session=session,project_id=project,resource_id=agent,
            candidate=candidate,principal=N(),reason="Invalid source")


@pytest.mark.asyncio
async def test_constituent_owner_snapshot_projection_keeps_native_hash_and_scope():
    import json
    from modules.agent.infra.database.frozen_snapshot_reader import AgentFrozenSnapshotReader
    project, agent, snapshot = uuid4(), uuid4(), uuid4()
    source = AgentReleaseModel(id=snapshot, project_id=project, agent_id=agent,
        version=snapshot.hex, status="archived", snapshot_kind="candidate",
        session_mode="stateless", name="Frozen", provider="custom", model="exact",
        runtime_config={"execution_strategy": "standard"})
    source.provider_model_id = uuid4()
    session = N(get=AsyncMock(return_value=source))
    reader = AgentFrozenSnapshotReader()
    projection = await reader.read(session, project_id=project, resource_id=agent,
        snapshot_id=snapshot, expected_kind="candidate")
    assert projection["runtime_digest"] == "sha256:" + hash_agent_execution_snapshot(frozen_release_entity(source))
    assert projection["runtime_snapshot"]["model"] == "exact"
    json.dumps(projection)
    for field, value in (("project_id", uuid4()), ("resource_id", uuid4()), ("expected_kind", "release")):
        arguments = dict(project_id=project, resource_id=agent, snapshot_id=snapshot, expected_kind="candidate")
        arguments[field] = value
        with pytest.raises(ConflictError, match="SOURCE_INVALID"):
            await reader.read(session, **arguments)
