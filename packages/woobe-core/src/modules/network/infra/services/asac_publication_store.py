"""Durable Network publication phases; each Agent remains its own write owner."""
from copy import deepcopy
from uuid import UUID, uuid5

from shared.contracts.asac import asac_digest
from shared.contracts.asac_constituent_publication import PublishFrozenConstituent
from shared.contracts.asac_publication import PublishASaCCandidate
from shared.contracts.errors import ConflictError, NotFoundError
from shared.infra.admin_idempotency import principal_identity
from shared.infra.asac_publication_store import ASaCPublicationStore, publication_output
from modules.network.infra.database.asac_models import (
    ASaCPublicationPreparationModel, ASaCConstituentPublicationModel,
)


def preparation_output(row):
    data = {"schema_version": "1.0", "kind": "Network", "publication_id": str(row.id),
        "project_id": str(row.project_id), "resource_id": str(row.resource_id), "resource_uid": str(row.resource_uid),
        "operation_id": str(row.operation_id), "candidate_id": str(row.candidate_id), "evaluation_id": str(row.evaluation_id),
        "state": row.state, "accepted": True, "published": False, "production_changed": False,
        "complete": row.state == "cancelled", "write_outcome": "committed", "prepared_constituents": len(row.children),
        "required_constituents": len(row.source["bindings"]), "error_code": row.error_code,
        "runtime_digest": row.source["runtime_digest"], "runtime_digest_scope": row.source["runtime_digest_scope"],
        "record_digest": row.source["record_digest"]}
    if row.state == "cancelled":
        data.update(actor=row.actor, reason=row.cancel_reason)
        data["receipt_digest"] = asac_digest("publication-cancellation", data)
    return data


class NetworkASaCPublicationStore(ASaCPublicationStore):
    def __init__(self, *, evaluations, publications, publisher, constituents):
        super().__init__(evaluations=evaluations, publications=publications, publisher=publisher)
        self.constituents = constituents

    async def publish(self, *, project_id, resource_id, principal, request):
        args = dict(project_id=project_id, resource_id=resource_id, principal=principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, **args, write=True)
            digest, replay = await self.drafts._operation(session, **args, request=request, action="publish")
            if replay is not None:
                return replay
            candidate, evaluation, record = await self._proof(session, project_id, resource_id, request)
            source = await self.publisher.capture(session=session, project_id=project_id,
                resource_id=resource_id, candidate=candidate)
        fingerprints = await self.evaluations._bindings(candidate, project_id, principal)
        # Constituent authority and native hashes are read through the Agent owner,
        # outside the Network transaction, before accepting durable phase identity.
        for binding in source["bindings"].values():
            proof = await self.constituents.inspect(project_id=project_id,
                resource_id=UUID(binding["agent_id"]), principal=principal,
                snapshot_id=UUID(binding["release_id"]), require_version=True)
            if proof["runtime_digest"] != binding["runtime_digest"]:
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED: exact constituent changed")
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, **args, write=True)
            digest, replay = await self.drafts._operation(session, **args, request=request, action="publish")
            if replay is not None:
                return replay
            candidate, evaluation, current = await self._proof(session, project_id, resource_id, request)
            captured = await self.publisher.capture(session=session, project_id=project_id,
                resource_id=resource_id, candidate=candidate)
            if fingerprints != candidate.runtime_fingerprints or current != record or captured != source:
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED")
            preparation = ASaCPublicationPreparationModel(project_id=project_id, resource_id=resource_id,
                resource_uid=candidate.resource_uid, candidate_id=candidate.id, evaluation_id=evaluation.id,
                actor=principal_identity(principal), operation_id=request.operation_id, request_digest=digest,
                request=request.model_dump(mode="json", exclude_none=True), source=source,
                children={}, state="preparing", error_code=None, cancel_reason=None)
            session.add(preparation)
            await session.flush()
            publication_id = preparation.id
            accepted = self.drafts._receipt(session, **args, request=request,
                digest=digest, result=preparation_output(preparation))
        # Any post-acceptance interruption retains the original accepted ledger.
        # It must not look like an unattempted/rejected write to the CLI.
        try:
            return await self.reconcile(**args, publication_id=publication_id)
        except Exception as exc:
            code = str(exc).partition(":")[0]
            if not code.startswith("ASAC_") or len(code) > 128 or not all(c.isupper() or c.isdigit() or c == "_" for c in code):
                code = "ASAC_PUBLICATION_PREPARATION_PENDING"
            try:
                async with self.drafts.transactions.begin() as session:
                    await self._authorize(session, **args, write=True)
                    row = await self._preparation(session, project_id=project_id,
                        resource_id=resource_id, publication_id=publication_id)
                    if row.state == "preparing":
                        row.error_code = code
            except Exception:
                # Revoked authority or failed storage cannot authorize a new
                # write. The committed original acceptance still remains.
                pass
            return accepted

    async def _preparation(self, session, *, project_id, resource_id, publication_id, allow_cancelled=False):
        row = await session.get(ASaCPublicationPreparationModel, publication_id, with_for_update=True)
        if row is None or row.project_id != project_id or row.resource_id != resource_id:
            raise NotFoundError("ASAC_PUBLICATION_UNAVAILABLE")
        if row.state == "cancelled" and not allow_cancelled:
            raise ConflictError("ASAC_PUBLICATION_CANCELLED: original preparation was closed without publication")
        return row

    async def reconcile(self, *, project_id, resource_id, publication_id, principal):
        args = dict(project_id=project_id, resource_id=resource_id, principal=principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, **args, write=True)
            preparation = await self._preparation(session, project_id=project_id,
                resource_id=resource_id, publication_id=publication_id)
            if preparation.actor != principal_identity(principal):
                raise ConflictError("ASAC_PUBLICATION_ACTOR_MISMATCH: only the original owner may resume these phases")
            finished = await session.get(self.publications, publication_id)
            if finished is not None:
                return publication_output(finished)
            request = PublishASaCCandidate.model_validate(preparation.request)
            candidate, evaluation, record = await self._proof(session, project_id, resource_id, request)
            source, completed = deepcopy(preparation.source), deepcopy(preparation.children)
            if await self.publisher.capture(session=session, project_id=project_id, resource_id=resource_id, candidate=candidate) != source:
                raise ConflictError("ASAC_PUBLICATION_SOURCE_INVALID")
        await self.evaluations._bindings(candidate, project_id, principal)
        for key in sorted(source["bindings"]):
            binding = source["bindings"][key]
            await self.evaluations._bindings(candidate, project_id, principal)
            child_operation = uuid5(request.operation_id, str(resource_id) + ":" + binding["agent_id"] + ":" + binding["release_id"])
            child_request = PublishFrozenConstituent(operation_id=child_operation,
                parent_operation_id=request.operation_id, parent_resource_id=resource_id,
                parent_candidate_id=request.candidate_id, parent_evaluation_id=request.evaluation_id,
                snapshot_id=UUID(binding["release_id"]), expected_runtime_digest=binding["runtime_digest"], reason=request.reason)
            receipt = await self.constituents.publish(project_id=project_id,
                resource_id=UUID(binding["agent_id"]), principal=principal, request=child_request)
            if key in completed and completed[key] != receipt:
                raise ConflictError("ASAC_PUBLICATION_SOURCE_INVALID: original constituent receipt differs")
            async with self.drafts.transactions.begin() as session:
                await self._authorize(session, **args, write=True)
                preparation = await self._preparation(session, project_id=project_id,
                    resource_id=resource_id, publication_id=publication_id)
                if key in preparation.children and preparation.children[key] != receipt:
                    raise ConflictError("ASAC_PUBLICATION_SOURCE_INVALID: original phase receipt differs")
                if preparation.state == "preparing":
                    preparation.children = {**preparation.children, key: receipt}
            completed[key] = receipt
        fingerprints = await self.evaluations._bindings(candidate, project_id, principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, **args, write=True)
            preparation = await self._preparation(session, project_id=project_id,
                resource_id=resource_id, publication_id=publication_id)
            finished = await session.get(self.publications, publication_id)
            if finished is not None:
                return publication_output(finished)
            candidate, evaluation, current = await self._proof(session, project_id, resource_id, request)
            if fingerprints != candidate.runtime_fingerprints or current != record or preparation.children != completed:
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED")
            native = await self.publisher.publish(session=session, project_id=project_id,
                resource_id=resource_id, candidate=candidate, principal=principal, reason=request.reason,
                source=source, children=completed)
            if native["runtime_digest"] != candidate.runtime_digest:
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED: native Release differs from qualification")
            row = self.publications(id=publication_id, project_id=project_id,
                resource_id=resource_id, resource_uid=candidate.resource_uid, candidate_id=candidate.id,
                evaluation_id=evaluation.id, release_id=native["release_id"], release_version=native["release_version"],
                revision_id=candidate.revision_id, actor=preparation.actor, operation_id=request.operation_id,
                request_digest=preparation.request_digest, reused=native["reused"], reason=request.reason, evidence={
                    "kind": "Network", "runtime_digest_scope": source["runtime_digest_scope"],
                    "record_digest": candidate.record_digest, "runtime_digest": candidate.runtime_digest,
                    "definition_digest": record["definition_digest"], "artifact_digest": record["artifact_digest"],
                    "binding_digest": evaluation.binding_digest, "suite_digest": evaluation.suite_digest,
                    "dataset_digest": evaluation.dataset_digest, "policy_digest": evaluation.policy_digest,
                    "constituent_releases": [{"node_id": key, "agent_id": item["resource_id"],
                        "source_snapshot_id": item["source_snapshot_id"], "release_id": item["release_id"],
                        "runtime_digest": item["runtime_digest"]} for key, item in sorted(completed.items())],
                    "git": {"status": "declared", **request.git.model_dump()} if request.git else {"status": "unavailable"}})
            session.add(row)
            await session.flush()
            for key, item in completed.items():
                session.add(ASaCConstituentPublicationModel(project_id=project_id, resource_id=resource_id,
                    publication_id=row.id, node_id=UUID(key), agent_id=UUID(item["resource_id"]),
                    source_snapshot_id=UUID(item["source_snapshot_id"]), release_id=UUID(item["release_id"]),
                    runtime_digest=item["runtime_digest"]))
            preparation.state, preparation.error_code = "published", None
            await session.flush()
            return publication_output(row)

    async def cancel(self, *, project_id, resource_id, publication_id, principal, request):
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True)
            row = await self._preparation(session, project_id=project_id,
                resource_id=resource_id, publication_id=publication_id, allow_cancelled=True)
            if row.actor != principal_identity(principal):
                raise ConflictError("ASAC_PUBLICATION_ACTOR_MISMATCH")
            if row.state == "published" or await session.get(self.publications, publication_id) is not None:
                raise ConflictError("ASAC_PUBLICATION_ALREADY_COMMITTED: cancellation cannot undo a published Release")
            if row.state == "cancelled":
                if row.cancel_reason != request.reason:
                    raise ConflictError("ASAC_OPERATION_CONFLICT: original cancellation reason differs")
                return preparation_output(row)
            row.state, row.error_code, row.cancel_reason = "cancelled", "ASAC_PUBLICATION_CANCELLED", request.reason
            await session.flush()
            return preparation_output(row)

    async def get(self, *, project_id, resource_id, publication_id, principal):
        async with self.drafts._read() as session:
            await self._authorize(session, project_id, resource_id, principal)
            finished = await session.get(self.publications, publication_id)
            if finished is not None and finished.project_id == project_id and finished.resource_id == resource_id:
                return publication_output(finished)
            row = await session.get(ASaCPublicationPreparationModel, publication_id)
            if row is None or row.project_id != project_id or row.resource_id != resource_id:
                raise NotFoundError("ASAC_PUBLICATION_UNAVAILABLE")
            return preparation_output(row)
