from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, func

from tests.unit.agent.test_asac_candidate_store import candidate_fixture
from shared.contracts.asac_evaluation import ASaCEvaluationSuite, EvaluateASaCCandidate
from shared.contracts.errors import ConflictError
from shared.infra.asac_candidate_store import seal_candidate
from shared.infra.asac_evaluation_store import ASaCEvaluationStore


@pytest.fixture
async def evaluation_fixture(candidate_fixture):
    candidates, drafts, sessions, tables, args, stage = candidate_fixture
    async with sessions.begin() as session:
        await session.run_sync(lambda sync: tables.ASaCEvaluationModel.__table__.create(sync.connection()))
    receipt = await candidates.stage(**args, request=stage, api_origin="https://woobe.invalid")
    candidate_id = UUID(receipt["candidate_id"])
    async with sessions.begin() as session:
        row = await session.get(tables.ASaCCandidateModel, candidate_id)
        snapshot_id = UUID(next(iter(row.snapshot_ids.values())))
        await seal_candidate(session, tables.ASaCCandidateModel, project_id=args["project_id"],
            resource_id=args["resource_id"], candidate_id=candidate_id,
            preparation_operation_id=row.preparation_operation_id, snapshot_id=snapshot_id,
            runtime_digest="sha256:" + "d" * 64, native_bindings={}, runtime_fingerprints={"provider": "version-1"})
    candidates.preparation.verify_runtime_bindings = AsyncMock(return_value={"provider": "version-1"})
    runs = {}
    async def execute_case(**kw):
        case = kw["case"]
        runs[case["run_id"]] = {"run_id":case["run_id"], "snapshot_id":str(snapshot_id),
            "state":"completed", "parsed_output":{"answer":"expected"}, "usage":{"total_tokens":17}}
    async def read_case(**kw):
        return runs.get(kw["case"]["run_id"])
    runtime = SimpleNamespace(execute_case=AsyncMock(side_effect=execute_case), read_case=AsyncMock(side_effect=read_case))
    store = ASaCEvaluationStore(candidates=candidates, evaluations=tables.ASaCEvaluationModel, runtime=runtime)
    suite = ASaCEvaluationSuite(schema_version="1.0", suite_id="support", suite_version="1", dataset_version="1",
        cases=[{"id":"question", "message":"Verify this exact candidate", "expected_output":{"answer":"expected"}}])
    request = EvaluateASaCCandidate(operation_id=uuid4(), suite=suite)
    yield store, args, candidate_id, request, runs, tables, sessions


@pytest.mark.asyncio
async def test_exact_candidate_evaluation_records_real_case_identity_and_original_replay(evaluation_fixture):
    store, args, candidate, request, runs, tables, sessions = evaluation_fixture
    receipt, accepted = await store.accept(**args, candidate_id=candidate, request=request)
    assert accepted and receipt["state"] == "accepted" and not receipt["published"]
    assert not runs and not receipt["complete"]
    assert await store.accept(**args, candidate_id=candidate, request=request) == (receipt, False)
    evaluation = await store.execute(**args, evaluation_id=UUID(receipt["evaluation_id"]))
    assert evaluation["state"] == "passed" and evaluation["complete"]
    assert evaluation["cases"][0]["usage"]["total_tokens"] == 17
    assert store.runtime.execute_case.await_count == 1
    assert await store.accept(**args, candidate_id=candidate, request=request) == (receipt, False)
    assert await store.reconcile(**args, evaluation_id=UUID(receipt["evaluation_id"])) == evaluation
    assert store.runtime.execute_case.await_count == 1
    with pytest.raises(ConflictError, match="OPERATION_CONFLICT"):
        await store.accept(**args, candidate_id=candidate, request=request.model_copy(update={"suite":request.suite.model_copy(update={"dataset_version":"2"})}))


@pytest.mark.asyncio
async def test_missing_wrong_or_failed_native_evidence_never_qualifies(evaluation_fixture):
    store, args, candidate, request, runs, tables, sessions = evaluation_fixture
    receipt, _ = await store.accept(**args, candidate_id=candidate, request=request)
    eid = UUID(receipt["evaluation_id"])
    assert (await store.reconcile(**args,evaluation_id=eid))["state"] == "accepted"
    assert store.runtime.execute_case.await_count == 0
    case = receipt["cases"][0]
    runs[case["run_id"]] = {"run_id":case["run_id"],"snapshot_id":str(uuid4()),"state":"completed"}
    with pytest.raises(ConflictError,match="EVIDENCE_INVALID"):
        await store.reconcile(**args,evaluation_id=eid)
    async with sessions() as session:
        source = await session.get(tables.ASaCCandidateModel,candidate)
        correct = str(source.root_snapshot_id)
    runs[case["run_id"]].update(snapshot_id=correct,state="failed")
    failed = await store.reconcile(**args,evaluation_id=eid)
    assert failed["state"] == "failed" and "RUNTIME_EXECUTION_FAILED" in failed["cases"][0]["errors"]
    assert store.runtime.execute_case.await_count == 0


@pytest.mark.asyncio
async def test_binding_race_after_validation_cannot_accept_evaluation(evaluation_fixture):
    store, args, candidate, request, runs, tables, sessions = evaluation_fixture
    async def racing(**kwargs):
        async with sessions.begin() as session:
            row = await session.get(tables.ASaCCandidateModel,candidate)
            row.runtime_fingerprints = {"provider":"changed"}
        return {"provider":"version-1"}
    store.candidates.preparation.verify_runtime_bindings.side_effect = racing
    with pytest.raises(ConflictError,match="BINDINGS_CHANGED"):
        await store.accept(**args,candidate_id=candidate,request=request)
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(tables.ASaCEvaluationModel)) == 0


def test_suite_digests_bind_declared_versions_to_exact_case_content():
    from pydantic import ValidationError
    suite = {"schema_version":"1.0","suite_id":"support","suite_version":"1","dataset_version":"1",
        "cases":[{"id":"question","message":"one","expected_output":{"ok":True}}]}
    first = ASaCEvaluationSuite.model_validate(suite)
    other = ASaCEvaluationSuite.model_validate({**suite,"cases":[{**suite["cases"][0],"message":"two"}]})
    assert first.evidence_digests()["dataset_digest"] != other.evidence_digests()["dataset_digest"]
    for invalid in [{**suite,"cases":[]}, {**suite,"passed":True}, {**suite,"policy_version":"skip-tests"},
                    {**suite,"cases":suite["cases"] * 2},
                    {**suite,"cases":[{**suite["cases"][0],"expected_output":float("nan")}]}]:
        with pytest.raises(ValidationError):
            ASaCEvaluationSuite.model_validate(invalid)


@pytest.mark.asyncio
async def test_started_case_cannot_be_claimed_twice(evaluation_fixture):
    store, args, candidate, request, runs, tables, sessions = evaluation_fixture
    receipt, _ = await store.accept(**args, candidate_id=candidate, request=request)
    eid = UUID(receipt["evaluation_id"])
    case = {**receipt["cases"][0], "state": "running"}
    await store._save_case(args["project_id"], args["resource_id"], eid, args["principal"], 0, case)
    with pytest.raises(ConflictError, match="ALREADY_STARTED"):
        await store.execute(**args, evaluation_id=eid)
    assert store.runtime.execute_case.await_count == 0


@pytest.mark.asyncio
async def test_binding_change_after_acceptance_is_durable_failed_evidence(evaluation_fixture):
    store, args, candidate, request, runs, tables, sessions = evaluation_fixture
    receipt, _ = await store.accept(**args, candidate_id=candidate, request=request)
    store.candidates.preparation.verify_runtime_bindings.side_effect = ConflictError("ASAC_RUNTIME_BINDINGS_CHANGED")
    eid = UUID(receipt["evaluation_id"])
    result = await store.execute(**args, evaluation_id=eid)
    assert result["state"] == "failed" and result["error_code"] == "ASAC_RUNTIME_BINDINGS_CHANGED"
    assert store.runtime.execute_case.await_count == 0
    assert await store.accept(**args, candidate_id=candidate, request=request) == (receipt, False)
    assert await store.reconcile(**args, evaluation_id=eid) == result
