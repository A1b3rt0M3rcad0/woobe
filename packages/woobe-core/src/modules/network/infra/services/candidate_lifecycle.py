"""Detached Network candidates bind only exact prepared native Agent snapshots."""
from uuid import UUID

from modules.network.application.portable_definition import compile_imported_network_definition
from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.environment_bindings import validate_network_environment_bindings
from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import NetworkVersionModel
from modules.network.infra.database.asac_models import ASaCCandidateModel
from modules.agent.contract_boundary import hash_agent_execution_snapshot
from modules.network.domain.execution_identity import NETWORK_RUNTIME_SCOPE, network_runtime_digest
from shared.contracts.errors import ConflictError
from shared.infra.asac_candidate_store import seal_candidate
from shared.presentation.contracts import OperationResult


class NetworkCandidateLifecycleHandler:
    def __init__(self, uow, owner, service):
        self.uow, self.owner, self.service = uow, owner, service

    async def handle(self, request):
        body, session = request.body, self.uow.session
        project, network_id = UUID(body["project_id"]), UUID(body["network_id"])
        evidence = await self.owner.inspect(session, project_id=project, resource_id=network_id,
            principal=request.principal, kind="Network", environment="staging",
            required_permission="network:read" if body["action"] == "resolve_candidate_root" else "network:version")
        if body["action"] == "resolve_candidate_root":
            return OperationResult(body={"success": True, "data": {"id": str(network_id), "revision": evidence["revision"]}})
        # Compile topology from sealed portable input. Snapshot choice is never
        # delegated to Default Draft/Staging selectors or mutable Agent fields.
        spec = body["portable_spec"]
        definition = compile_imported_network_definition(spec, network_id=network_id,
            agents=body["agents"], snapshots={key: {source: value for source in ("staging", "release")}
                for key, value in body["snapshots"].items()})
        for node, portable in zip(definition["nodes"], spec["nodes"], strict=True):
            node["binding"] = {"source": "candidate", "release_id": body["snapshots"][portable["agent_ref"]]}
        parsed = self.service._definition(definition)
        validate_network_environment_bindings(parsed, "candidate")
        bindings = {}
        for node in parsed.nodes:
            release = await self.service._get_release(session, node.binding.release_id, project, node.agent_id, lock=True)
            if release is None or release.snapshot_kind != "candidate":
                raise ConflictError("ASAC_CANDIDATE_EVIDENCE_INVALID: exact Agent candidate is unavailable")
            bindings[str(node.id)] = self.service._release_binding_payload(node.id, node.agent_id, release, "candidate")
            bindings[str(node.id)]["snapshot_override"]["external_context_contract"] = release.external_context_contract
            bindings[str(node.id)]["runtime_digest"] = "sha256:" + hash_agent_execution_snapshot(release)
        digest = composition_hash(parsed, bindings)
        snapshot_id = UUID(body["candidate_snapshot_id"])
        version = await session.get(NetworkVersionModel, snapshot_id)
        if body["action"] == "create_candidate_snapshot":
            if version is not None:
                if (version.project_id != project or version.network_id != network_id or version.kind != "candidate"
                    or version.definition != definition or version.resolved_bindings != bindings or version.composition_hash != digest):
                    raise ConflictError("ASAC_CANDIDATE_IMMUTABLE: Network snapshot identity has another composition")
            else:
                contract = await self.service._effective_external_context_contract(session,
                    definition=parsed, bindings=bindings, version=None)
                version = NetworkVersionModel(id=snapshot_id, project_id=project, network_id=network_id,
                    kind="candidate", version=snapshot_id.hex, definition=definition, resolved_bindings=bindings,
                    composition_hash=digest, effective_external_context_contract=contract,
                    created_by=None, rollback_of_version_id=None, source_version_id=None)
                session.add(version)
                await session.flush()
            result = {"id": str(version.id), "network_id": str(network_id), "snapshot_kind": "candidate",
                "runtime_digest": network_runtime_digest(parsed, bindings, version.effective_external_context_contract),
                "configuration_ready": True, "execution_ready": True}
        else:
            if (version is None or version.project_id != project or version.network_id != network_id
                or version.kind != "candidate" or version.definition != definition or version.resolved_bindings != bindings
                or version.composition_hash != digest):
                raise ConflictError("ASAC_CANDIDATE_EVIDENCE_INVALID: exact Network candidate differs from its sealed closure")
            runtime_digest = network_runtime_digest(parsed, bindings, version.effective_external_context_contract)
            if runtime_digest != body["expected_runtime_digest"]:
                raise ConflictError("ASAC_CANDIDATE_EVIDENCE_INVALID: executable Network snapshot changed")
            result = await seal_candidate(session, ASaCCandidateModel, project_id=project, resource_id=network_id,
                candidate_id=UUID(body["candidate_id"]), preparation_operation_id=UUID(body["preparation_operation_id"]),
                snapshot_id=snapshot_id, runtime_digest=runtime_digest, native_bindings=bindings,
                runtime_fingerprints=body["runtime_fingerprints"], runtime_digest_scope=NETWORK_RUNTIME_SCOPE)
            result.update(configuration_ready=True, execution_ready=True)
        return OperationResult(body={"success": True, "data": result})
