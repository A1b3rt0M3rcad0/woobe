from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.network.infra.services.candidate_evaluation_runtime import validate_candidate_case_admission
from shared.contracts.errors import ConflictError


@pytest.fixture
def admission():
    project, network, evaluation_id, candidate_id, snapshot, run_id = (uuid4() for _ in range(6))
    evaluation = N(id=evaluation_id,project_id=project,resource_id=network,state="running",candidate_id=candidate_id,
        runtime_digest="runtime",record_digest="record",cases=[{"id":"case","state":"running","run_id":str(run_id)}],
        suite={"cases":[{"id":"case","message":"hello"}]})
    candidate = N(project_id=project,resource_id=network,state="ready",root_snapshot_id=snapshot,runtime_digest="runtime",record_digest="record")
    opening = N(project_id=project,network_id=network,network_version_id=snapshot,origin="asac_evaluation",
        external_session_id="asac-evaluation:"+str(evaluation_id)+":case")
    rows={evaluation_id:evaluation,candidate_id:candidate}
    async def get(model,key,**kwargs): return rows.get(key)
    session=N(get=AsyncMock(side_effect=get))
    args=dict(project_id=project,network_id=network,network_session=opening,message="hello",
        request={"evaluation_id":str(evaluation_id),"case_id":"case"})
    return session,args,evaluation,candidate,opening,run_id


@pytest.mark.asyncio
async def test_server_case_admission_retains_original_run_identity(admission):
    session,args,evaluation,candidate,opening,run_id=admission
    assert await validate_candidate_case_admission(session,**args)==run_id
    assert session.get.call_args_list[0].kwargs["with_for_update"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("target,field,value",[
    ("evaluation","state","accepted"),("candidate","project_id",uuid4()),
    ("candidate","resource_id",uuid4()),("candidate","root_snapshot_id",uuid4()),
    ("candidate","runtime_digest","changed"),("candidate","record_digest","changed"),
    ("opening","project_id",uuid4()),("opening","network_id",uuid4()),
    ("opening","origin","api"),("opening","external_session_id","invented"),
])
async def test_candidate_admission_cannot_cross_scope_or_evidence(admission,target,field,value):
    session,args,evaluation,candidate,opening,run_id=admission
    setattr({"evaluation":evaluation,"candidate":candidate,"opening":opening}[target],field,value)
    with pytest.raises(ConflictError,match="ADMISSION_INVALID"):
        await validate_candidate_case_admission(session,**args)


@pytest.mark.asyncio
async def test_ordinary_request_cannot_enter_candidate_session(admission):
    session,args,*_=admission
    args["request"]=None
    with pytest.raises(ConflictError,match="ADMISSION_REQUIRED"):
        await validate_candidate_case_admission(session,**args)
    session.get.assert_not_awaited()
