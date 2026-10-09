"""Candidate Network execution uses the native acceptance outbox and worker."""
import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select

from modules.network.infra.database.asac_models import ASaCCandidateModel, ASaCEvaluationModel
from modules.network.infra.database.models import NetworkExecutionModel, NetworkSessionModel, NetworkVersionModel
from shared.contracts.errors import ConflictError
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


async def validate_candidate_case_admission(session, *, project_id, network_id, network_session, message, request):
    if not request:
        raise ConflictError("ASAC_EVALUATION_ADMISSION_REQUIRED: candidate Sessions cannot accept ordinary Runs")
    evaluation = await session.get(ASaCEvaluationModel, UUID(request["evaluation_id"]), with_for_update=True)
    if (evaluation is None or evaluation.project_id != project_id or evaluation.resource_id != network_id
        or evaluation.state != "running"):
        raise ConflictError("ASAC_EVALUATION_ADMISSION_INVALID")
    candidate = await session.get(ASaCCandidateModel, evaluation.candidate_id)
    pairs = [(case, specification) for case, specification in zip(evaluation.cases, evaluation.suite["cases"], strict=True)
        if case["id"] == request["case_id"]]
    if (candidate is None or candidate.state != "ready" or candidate.project_id != project_id
        or candidate.resource_id != network_id or candidate.root_snapshot_id != network_session.network_version_id
        or network_session.project_id != project_id or network_session.network_id != network_id
        or network_session.origin != "asac_evaluation"
        or candidate.runtime_digest != evaluation.runtime_digest or candidate.record_digest != evaluation.record_digest or len(pairs) != 1):
        raise ConflictError("ASAC_EVALUATION_ADMISSION_INVALID")
    case, specification = pairs[0]
    if (case["state"] != "running" or specification["message"] != message
        or network_session.external_session_id != "asac-evaluation:" + str(evaluation.id) + ":" + case["id"]):
        raise ConflictError("ASAC_EVALUATION_ADMISSION_INVALID")
    return UUID(case["run_id"])


class NetworkCandidateEvaluationRuntime:
    def __init__(self, *, sessions, service, journal):
        self.sessions, self.service, self.journal = sessions, service, journal

    async def execute_case(self, *, project_id, resource_id, evaluation, candidate, case, specification, principal):
        session_id = uuid4()
        async with self.sessions.begin() as session:
            current = await session.get(ASaCEvaluationModel, evaluation.id, with_for_update=True)
            frozen = await session.get(NetworkVersionModel, candidate.root_snapshot_id)
            if (current is None or current.state != "running" or current.project_id != project_id
                or current.resource_id != resource_id or frozen is None or frozen.kind != "candidate"
                or frozen.network_id != resource_id or frozen.project_id != project_id):
                raise ConflictError("ASAC_EVALUATION_ADMISSION_INVALID")
            session.add(NetworkSessionModel(id=session_id, network_id=resource_id,
                project_id=project_id, network_version_id=frozen.id, environment="staging",
                title="Candidate evaluation", status="active", origin="asac_evaluation",
                external_session_id="asac-evaluation:" + str(evaluation.id) + ":" + case["id"]))
        await self.service.submit_execution(network_id=resource_id, project_id=project_id,
            network_session_id=session_id, message=specification["message"],
            external_context=specification["external_context"], idempotency_key="asac-evaluation:" + case["run_id"],
            _candidate_evaluation={"evaluation_id": str(evaluation.id), "case_id": case["id"]})
        # Native workers own execution. Timeout leaves its original durable Run
        # inspectable; reconciliation never submits another execution.
        for _ in range(600):
            proof = await self.read_case(project_id=project_id, resource_id=resource_id,
                evaluation=evaluation, candidate=candidate, case=case, specification=specification)
            if proof and proof["state"] in {"completed", "failed", "cancelled", "timed_out", "uncertain"}:
                return proof
            await asyncio.sleep(0.5)

    async def read_case(self, *, project_id, resource_id, evaluation, candidate, case, specification):
        async with self.sessions() as session:
            run = await session.get(NetworkExecutionModel, UUID(case["run_id"]))
            if run is None:
                return None
            opening = await session.get(NetworkSessionModel, run.network_session_id)
            if (run.project_id != project_id or run.network_id != resource_id
                or run.network_version_id != candidate.root_snapshot_id or opening is None
                or opening.origin != "asac_evaluation" or opening.project_id != project_id
                or opening.external_session_id != "asac-evaluation:" + str(evaluation.id) + ":" + case["id"]
                or run.input_message != specification["message"]):
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_INVALID: native Network Run scope differs")
            status, result, storage = run.status, {"answer": run.output_message,
                "parsed_output": getattr(run, "parsed_output", None),
                "output_parse_error": getattr(run, "output_parse_error", None)}, run.storage_version
        if storage == EVENT_JOURNAL_STORAGE_VERSION:
            if self.journal is None:
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_UNAVAILABLE")
            state = await self.journal.get_state(UUID(case["run_id"]))
            if state is None or state.terminal_sequence is None:
                return None
            if (state.run_id != UUID(case["run_id"]) or state.run_kind != "network"
                or state.storage_version != EVENT_JOURNAL_STORAGE_VERSION
                or state.terminal_sequence > state.durable_sequence):
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_INVALID")
            events = await self.journal.list_events(UUID(case["run_id"]),
                after_sequence=state.terminal_sequence - 1, through_sequence=state.terminal_sequence, limit=1)
            if (len(events) != 1 or events[0].run_id != state.run_id or events[0].run_kind != "network"
                or events[0].sequence != state.terminal_sequence
                or events[0].storage_version != EVENT_JOURNAL_STORAGE_VERSION
                or events[0].event_type != "run." + str(state.terminal_status)):
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_UNAVAILABLE")
            status, result = state.terminal_status, dict(events[0].payload)
            invocations = {}
            cursor = 0
            for _ in range(40):
                page = await self.journal.list_events(state.run_id, after_sequence=cursor,
                    through_sequence=state.terminal_sequence, limit=500)
                if not page:
                    raise ConflictError("ASAC_EVALUATION_EVIDENCE_UNAVAILABLE: incomplete invocation journal")
                for event in page:
                    if (event.run_id != state.run_id or event.run_kind != "network"
                        or event.sequence != cursor + 1):
                        raise ConflictError("ASAC_EVALUATION_EVIDENCE_INVALID: invocation journal gap")
                    cursor = event.sequence
                    invocation = event.payload.get("invocation")
                    if event.event_type.startswith("agent.invocation.") and isinstance(invocation, dict):
                        invocations[str(invocation["id"])] = invocation
                if cursor == state.terminal_sequence:
                    break
            if cursor != state.terminal_sequence:
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_UNAVAILABLE: invocation journal exceeds evaluation limit")
            roots = [item for item in invocations.values() if item.get("depth") == 0]
            if status == "completed" and (len(roots) != 1 or roots[0].get("status") != "completed"):
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_INVALID: completed root invocation is absent")
            if roots:
                result["parsed_output"] = roots[0].get("parsed_output")
                result["output_parse_error"] = roots[0].get("output_parse_error")
            usages = [item.get("usage") or {} for item in invocations.values()]
            totals = {}
            for field in ("input_tokens", "output_tokens", "total_tokens", "cost_usd"):
                values = [item.get(field) for item in usages]
                if not values or any(value is None for value in values):
                    totals[field] = None
                elif field == "cost_usd":
                    totals[field] = str(sum((Decimal(str(value)) for value in values), Decimal(0)))
                else:
                    totals[field] = sum(values)
            result["usage"] = totals
        return {"run_id": case["run_id"], "snapshot_id": str(candidate.root_snapshot_id),
            "state": status, "answer": result.get("answer", result.get("output_message", result.get("output"))),
            "parsed_output": result.get("parsed_output"), "output_parse_error": result.get("output_parse_error"),
            "usage": result.get("usage")}


class NetworkCandidateRuntimeAdmissionReader:
    def __init__(self, sessions):
        self.sessions = sessions

    async def read(self, *, project_id, network_id, execution_id, agent_id, snapshot_id):
        async with self.sessions() as session:
            run = await session.get(NetworkExecutionModel, execution_id)
            version = await session.get(NetworkVersionModel, run.network_version_id) if run else None
            if version is None or version.kind != "candidate":
                return None
            opening = await session.get(NetworkSessionModel, run.network_session_id)
            if (run.project_id != project_id or run.network_id != network_id or opening is None
                or opening.origin != "asac_evaluation" or opening.project_id != project_id
                or version.project_id != project_id or version.network_id != network_id
                or opening.network_id != network_id or opening.network_version_id != version.id
                or run.status not in {"queued", "running"}):
                raise ConflictError("ASAC_EVALUATION_ADMISSION_INVALID")
            candidates = (await session.scalars(select(ASaCCandidateModel).where(
                ASaCCandidateModel.project_id == project_id, ASaCCandidateModel.resource_id == network_id,
                ASaCCandidateModel.root_snapshot_id == version.id))).all()
            if len(candidates) != 1 or candidates[0].state != "ready":
                raise ConflictError("ASAC_EVALUATION_ADMISSION_INVALID")
            candidate = candidates[0]
            evaluations = (await session.scalars(select(ASaCEvaluationModel).where(
                ASaCEvaluationModel.project_id == project_id, ASaCEvaluationModel.resource_id == network_id,
                ASaCEvaluationModel.candidate_id == candidate.id, ASaCEvaluationModel.state == "running"))).all()
            matching = [evaluation for evaluation in evaluations for case in evaluation.cases
                if case["run_id"] == str(run.id) and case["state"] == "running"
                and opening.external_session_id == "asac-evaluation:" + str(evaluation.id) + ":" + case["id"]]
            bindings = [binding for binding in version.resolved_bindings.values()
                if binding.get("agent_id") == str(agent_id) and binding.get("release_id") == str(snapshot_id)
                and binding.get("binding_source") == "candidate"]
            if len(matching) != 1 or not bindings:
                raise ConflictError("ASAC_EVALUATION_ADMISSION_INVALID")
            evaluation = matching[0]
            if evaluation.runtime_digest != candidate.runtime_digest or evaluation.record_digest != candidate.record_digest:
                raise ConflictError("ASAC_EVALUATION_ADMISSION_INVALID")
            return {"evaluation_id": evaluation.id, "runtime_digest": evaluation.runtime_digest,
                "record_digest": evaluation.record_digest, "binding_digest": evaluation.binding_digest}
