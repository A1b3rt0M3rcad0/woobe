"""SQL completion cannot replace missing or wrongly scoped native journal proof."""
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.execution.candidate_evaluation_runtime import AgentCandidateEvaluationRuntime
from shared.contracts.errors import ConflictError
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


@pytest.fixture
def evidence():
    project, resource, evaluation_id, snapshot, run_id = (uuid4() for _ in range(5))
    candidate = N(root_snapshot_id=snapshot)
    evaluation = N(id=evaluation_id, runtime_digest="runtime", record_digest="record", binding_digest="bindings")
    case = {"run_id":str(run_id)}
    run = N(project_id=project, agent_id=resource, agent_release_id=snapshot,
        origin="asac_evaluation", input_message="hello", status="completed", result={"answer":"SQL projection"},
        usage=None, storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        execution_snapshot={"asac":{"evaluation_id":str(evaluation_id),"runtime_digest":"runtime","record_digest":"record","binding_digest":"bindings"}})
    class Uow:
        session = N(get=AsyncMock(return_value=run))
        def mark_read_only(self): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
    state = N(run_id=run_id, run_kind="agent", storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        terminal_sequence=7,durable_sequence=7,terminal_status="completed")
    event = N(run_id=run_id, run_kind="agent", storage_version=EVENT_JOURNAL_STORAGE_VERSION,
        sequence=7,event_type="run.completed",payload={"answer":"durable answer","usage":{"total_tokens":31}})
    journal=N(get_state=AsyncMock(return_value=state),list_events=AsyncMock(return_value=[event]))
    runtime=AgentCandidateEvaluationRuntime(uow_factory=Uow,handler=AsyncMock(),journal=journal)
    kwargs=dict(project_id=project,resource_id=resource,evaluation=evaluation,candidate=candidate,
        case=case,specification={"message":"hello"})
    return runtime,kwargs,run,state,event


@pytest.mark.asyncio
async def test_native_journal_is_the_completion_and_usage_authority(evidence):
    runtime,kwargs,run,state,event=evidence
    proof=await runtime.read_case(**kwargs)
    assert proof["answer"]=="durable answer" and proof["usage"]["total_tokens"]==31
    assert runtime.handler.await_count==0
    assert runtime.journal.list_events.call_args.kwargs == {"after_sequence":6,"through_sequence":7,"limit":1}


@pytest.mark.asyncio
async def test_sql_terminal_projection_without_durable_fact_stays_incomplete(evidence):
    runtime,kwargs,run,state,event=evidence
    runtime.journal.get_state.return_value=None
    assert await runtime.read_case(**kwargs) is None
    runtime.journal.get_state.return_value=state
    state.terminal_sequence=None
    assert await runtime.read_case(**kwargs) is None
    runtime.journal.list_events.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("target,field,value",[
    ("run","agent_release_id",uuid4()),("run","origin","api"),
    ("state","run_id",uuid4()),("state","run_kind","network"),
    ("state","durable_sequence",6),("event","sequence",6),
    ("event","run_id",uuid4()),("event","event_type","run.failed"),
])
async def test_wrong_scope_or_sequence_never_qualifies(evidence,target,field,value):
    runtime,kwargs,run,state,event=evidence
    setattr({"run":run,"state":state,"event":event}[target],field,value)
    with pytest.raises(ConflictError,match="EVIDENCE_(INVALID|UNAVAILABLE)"):
        await runtime.read_case(**kwargs)
    runtime.handler.assert_not_awaited()
