"""Owner evaluation receipts and case evidence, with no provider I/O under SQL."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select

from shared.contracts.asac import asac_digest
from shared.contracts.errors import ConflictError, NotFoundError
from shared.infra.admin_idempotency import principal_identity


def evaluation_output(row):
    return {"schema_version": "1.0", "evaluation_id": str(row.id),
        "candidate_id": str(row.candidate_id), "resource_id": str(row.resource_id),
        "operation_id": str(row.operation_id), "write_outcome": "committed",
        "state": row.state, "runtime_digest": row.runtime_digest,
        "record_digest": row.record_digest, "binding_digest": row.binding_digest,
        "suite_digest": row.suite_digest, "dataset_digest": row.dataset_digest,
        "policy_digest": row.policy_digest,
        "suite_id": row.suite["suite_id"], "suite_version": row.suite["suite_version"],
        "dataset_version": row.suite["dataset_version"], "policy_version": row.suite["policy_version"],
        "identity_claims": "declared", "content_digests": "server_verified",
        "cases": row.cases, "error_code": row.error_code,
        "published": False, "production_changed": False,
        "complete": row.state in {"passed", "failed", "uncertain"}}


class ASaCEvaluationStore:
    def __init__(self, *, candidates, evaluations, runtime):
        self.candidates, self.evaluations, self.runtime = candidates, evaluations, runtime
        self.drafts = candidates.drafts

    async def _authorize(self, session, project_id, resource_id, principal, *, execute=False, lock=False):
        await self.drafts.owner.inspect(session, project_id=project_id, resource_id=resource_id,
            principal=principal, kind=self.drafts.kind, environment="staging", lock=lock,
            required_permission="run:execute" if execute else "run:read")

    async def _candidate(self, session, project_id, resource_id, candidate_id):
        row = await session.get(self.candidates.candidates, candidate_id)
        if row is None or row.project_id != project_id or row.resource_id != resource_id:
            raise NotFoundError("ASAC_CANDIDATE_UNAVAILABLE")
        if row.state != "ready" or not row.root_snapshot_id or not row.runtime_digest:
            raise ConflictError("ASAC_CANDIDATE_NOT_READY: complete native preparation before evaluation")
        return row

    async def _bindings(self, candidate, project_id, principal):
        return await self.candidates.preparation.verify_runtime_bindings(project_id=project_id,
            candidate_id=candidate.id, preparation_operation_id=candidate.preparation_operation_id,
            principal=principal, expected_fingerprints=candidate.runtime_fingerprints)

    async def accept(self, *, project_id, resource_id, candidate_id, principal, request):
        action = "evaluate:" + str(candidate_id)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, execute=True, lock=True)
            digest, replay = await self.drafts._operation(session, project_id=project_id,
                resource_id=resource_id, principal=principal, request=request, action=action)
            if replay is not None:
                return replay, False
            candidate = await self._candidate(session, project_id, resource_id, candidate_id)
        fingerprints = await self._bindings(candidate, project_id, principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, execute=True, lock=True)
            digest, replay = await self.drafts._operation(session, project_id=project_id,
                resource_id=resource_id, principal=principal, request=request, action=action)
            if replay is not None:
                return replay, False
            candidate = await self._candidate(session, project_id, resource_id, candidate_id)
            if fingerprints != candidate.runtime_fingerprints:
                raise ConflictError("ASAC_RUNTIME_BINDINGS_CHANGED")
            cases = [{"id": case.id, "run_id": str(uuid4()), "state": "pending"} for case in request.suite.cases]
            row = self.evaluations(project_id=project_id, resource_id=resource_id,
                candidate_id=candidate_id, actor=principal_identity(principal), operation_id=request.operation_id,
                request_digest=digest, state="accepted", suite=request.suite.model_dump(),
                **request.suite.evidence_digests(), runtime_digest=candidate.runtime_digest,
                record_digest=candidate.record_digest, binding_digest=asac_digest("runtime-bindings", fingerprints),
                cases=cases)
            session.add(row)
            await session.flush()
            receipt = self.drafts._receipt(session, project_id=project_id, resource_id=resource_id,
                principal=principal, request=request, digest=digest, result=evaluation_output(row))
            return receipt, True

    async def _read(self, project_id, resource_id, evaluation_id, principal, *, execute=False):
        async with self.drafts._read() as session:
            await self._authorize(session, project_id, resource_id, principal, execute=execute)
            row = await session.get(self.evaluations, evaluation_id)
            if row is None or row.project_id != project_id or row.resource_id != resource_id:
                raise NotFoundError("ASAC_EVALUATION_UNAVAILABLE")
            candidate = await self._candidate(session, project_id, resource_id, row.candidate_id)
            # Agent read scopes rollback on exit. Detach values while the scope
            # is alive rather than handing expired ORM rows to runtime I/O.
            def detached(value):
                return SimpleNamespace(**{column.key: deepcopy(getattr(value, column.key))
                    for column in value.__table__.columns})
            return detached(row), detached(candidate)

    async def get(self, *, project_id, resource_id, evaluation_id, principal):
        row, _ = await self._read(project_id, resource_id, evaluation_id, principal)
        return evaluation_output(row)

    async def _save_case(self, project_id, resource_id, evaluation_id, principal, index, case):
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, execute=True, lock=True)
            row = await session.get(self.evaluations, evaluation_id, with_for_update=True)
            if row is None or row.project_id != project_id or row.resource_id != resource_id:
                raise NotFoundError("ASAC_EVALUATION_UNAVAILABLE")
            if row.state in {"passed", "failed", "uncertain"}:
                raise ConflictError("ASAC_EVALUATION_IMMUTABLE")
            cases = deepcopy(row.cases)
            if cases[index]["run_id"] != case["run_id"] or cases[index]["id"] != case["id"]:
                raise ConflictError("ASAC_EVALUATION_CASE_MISMATCH")
            if cases[index]["state"] != "pending" or case["state"] != "running":
                raise ConflictError("ASAC_EVALUATION_ALREADY_STARTED")
            cases[index] = case
            row.cases, row.state = cases, "running"
            await session.flush()

    async def _binding_failure(self, project_id, resource_id, evaluation_id, principal):
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, execute=True, lock=True)
            row = await session.get(self.evaluations, evaluation_id, with_for_update=True)
            if row is None or row.project_id != project_id or row.resource_id != resource_id:
                raise NotFoundError("ASAC_EVALUATION_UNAVAILABLE")
            if row.state not in {"passed", "failed", "uncertain"}:
                row.state, row.error_code = "failed", "ASAC_RUNTIME_BINDINGS_CHANGED"
                row.cases = [{**case, "state": "failed", "errors": ["ASAC_RUNTIME_BINDINGS_CHANGED"]}
                    for case in row.cases]
                await session.flush()
            return evaluation_output(row)

    async def execute(self, *, project_id, resource_id, evaluation_id, principal):
        # Only the acceptor calls this. Reconcile reads original native Runs;
        # it cannot invoke this method or start another provider execution.
        row, candidate = await self._read(project_id, resource_id, evaluation_id, principal, execute=True)
        for index, specification in enumerate(row.suite["cases"]):
            case = dict(row.cases[index])
            if case["state"] != "pending":
                raise ConflictError("ASAC_EVALUATION_ALREADY_STARTED")
            try:
                await self._bindings(candidate, project_id, principal)
            except ConflictError:
                return await self._binding_failure(project_id, resource_id, evaluation_id, principal)
            case["state"] = "running"
            await self._save_case(project_id, resource_id, evaluation_id, principal, index, case)
            try:
                await self.runtime.execute_case(project_id=project_id, resource_id=resource_id,
                    evaluation=row, candidate=candidate, case=case, specification=specification, principal=principal)
            except Exception:
                # Provider/Tool errors can contain secret material. The original
                # durable Run is the outcome authority, never exception text.
                pass
        return await self.reconcile(project_id=project_id, resource_id=resource_id,
            evaluation_id=evaluation_id, principal=principal)

    async def reconcile(self, *, project_id, resource_id, evaluation_id, principal):
        row, candidate = await self._read(project_id, resource_id, evaluation_id, principal, execute=True)
        if row.state in {"passed", "failed", "uncertain"}:
            return evaluation_output(row)
        cases = []
        for case, specification in zip(row.cases, row.suite["cases"], strict=True):
            evidence = await self.runtime.read_case(project_id=project_id, resource_id=resource_id,
                evaluation=row, candidate=candidate, case=case, specification=specification)
            result = dict(case)
            if evidence is None or evidence.get("state") not in {"completed", "failed", "cancelled", "uncertain", "timed_out"}:
                return evaluation_output(row)
            errors = []
            if evidence.get("run_id") != case["run_id"] or evidence.get("snapshot_id") != str(candidate.root_snapshot_id):
                raise ConflictError("ASAC_EVALUATION_EVIDENCE_INVALID: native Run belongs to another case or snapshot")
            if evidence["state"] != "completed": errors.append("RUNTIME_EXECUTION_FAILED")
            if evidence.get("output_parse_error"): errors.append("OUTPUT_VALIDATION_FAILED")
            expected = specification.get("expected_output")
            actual = evidence.get("parsed_output")
            if actual is None: actual = {"answer": evidence.get("answer")}
            if expected is not None and asac_digest("evaluation-output", actual) != asac_digest("evaluation-output", expected):
                errors.append("EXPECTED_OUTPUT_MISMATCH")
            result.update(state="failed" if errors else "passed", errors=errors,
                evidence_digest=asac_digest("evaluation-case", evidence), usage=evidence.get("usage"))
            cases.append(result)
        try:
            fingerprints = await self._bindings(candidate, project_id, principal)
        except ConflictError:
            return await self._binding_failure(project_id, resource_id, evaluation_id, principal)
        if asac_digest("runtime-bindings", fingerprints) != row.binding_digest:
            return await self._binding_failure(project_id, resource_id, evaluation_id, principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, execute=True, lock=True)
            current = await session.get(self.evaluations, evaluation_id, with_for_update=True)
            if current.state in {"passed", "failed", "uncertain"}:
                return evaluation_output(current)
            current.cases, current.state = cases, "passed" if all(case["state"] == "passed" for case in cases) else "failed"
            await session.flush()
            return evaluation_output(current)
