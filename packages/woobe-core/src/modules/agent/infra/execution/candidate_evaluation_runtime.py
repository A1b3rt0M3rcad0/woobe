"""Exact native Agent Runs; evaluation evidence is read from durable outcomes."""
from uuid import UUID

from modules.agent.application.interfaces.candidate_execution import CandidateExecutionGrant, candidate_execution
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.infra.database.run_models import AgentRunModel
from shared.contracts.errors import ConflictError
from shared.presentation.contracts import OperationRequest
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION


class AgentCandidateEvaluationRuntime:
    def __init__(self, *, uow_factory, handler, journal):
        self.uow_factory, self.handler, self.journal = uow_factory, handler, journal

    async def execute_case(self, *, project_id, resource_id, evaluation, candidate, case, specification, principal):
        grant = CandidateExecutionGrant(project_id=project_id, agent_id=resource_id,
            snapshot_id=candidate.root_snapshot_id, evaluation_id=evaluation.id,
            run_id=UUID(case["run_id"]), runtime_digest=evaluation.runtime_digest,
            record_digest=evaluation.record_digest, binding_digest=evaluation.binding_digest)
        token = candidate_execution.set(grant)
        execution_token = current_execution.set(new_execution_context())
        try:
            return await self.handler(OperationRequest(principal=principal,
                body={"project_id": project_id, "agent_id": resource_id,
                    "loaded_release_id": candidate.root_snapshot_id, "execution_context": "staging",
                    "message": specification["message"], "external_context": specification["external_context"],
                    "metadata": {"source": "asac_evaluation", "evaluation_id": str(evaluation.id), "case_id": case["id"]}}))
        finally:
            current_execution.reset(execution_token)
            candidate_execution.reset(token)

    async def read_case(self, *, project_id, resource_id, evaluation, candidate, case, specification):
        uow = self.uow_factory()
        uow.mark_read_only()
        async with uow:
            run = await uow.session.get(AgentRunModel, UUID(case["run_id"]))
            if run is None:
                return None
            scope = run.execution_snapshot.get("asac", {})
            if (run.project_id != project_id or run.agent_id != resource_id
                or run.agent_release_id != candidate.root_snapshot_id or run.origin != "asac_evaluation"
                or run.input_message != specification["message"]
                or scope.get("evaluation_id") != str(evaluation.id)
                or scope.get("binding_digest") != evaluation.binding_digest
                or scope.get("runtime_digest") != evaluation.runtime_digest
                or scope.get("record_digest") != evaluation.record_digest):
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_INVALID: native Agent Run scope differs")
            status, result, usage, storage = run.status, dict(run.result or {}), run.usage, run.storage_version
        if storage == EVENT_JOURNAL_STORAGE_VERSION:
            if self.journal is None:
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_UNAVAILABLE: durable Run journal is unavailable")
            state = await self.journal.get_state(UUID(case["run_id"]))
            if state is None or state.terminal_sequence is None:
                return None
            if (state.run_id != UUID(case["run_id"]) or state.run_kind != "agent"
                or state.storage_version != EVENT_JOURNAL_STORAGE_VERSION
                or state.terminal_sequence > state.durable_sequence):
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_INVALID: terminal journal scope differs")
            events = await self.journal.list_events(UUID(case["run_id"]),
                after_sequence=state.terminal_sequence - 1, through_sequence=state.terminal_sequence, limit=1)
            if (len(events) != 1 or events[0].sequence != state.terminal_sequence
                or events[0].run_id != UUID(case["run_id"]) or events[0].run_kind != "agent"
                or events[0].storage_version != EVENT_JOURNAL_STORAGE_VERSION
                or events[0].event_type != "run." + str(state.terminal_status)):
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_UNAVAILABLE: terminal Run journal fact is missing")
            status, result = state.terminal_status, dict(events[0].payload)
            usage = result.get("usage")
        return {"run_id": case["run_id"], "snapshot_id": str(candidate.root_snapshot_id),
            "state": status, "answer": result.get("answer"), "parsed_output": result.get("parsed_output"),
            "output_parse_error": result.get("output_parse_error"), "usage": usage}
