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
