"""Network-owned immutable publication from an exact tested frozen closure."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select

from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.environment_bindings import validate_network_environment_bindings
from modules.network.domain.execution_identity import NETWORK_RUNTIME_SCOPE, network_runtime_digest
from modules.network.domain.external_context_contract import classify_effective_external_context_change, strongest_release_change
from modules.network.domain.graph import composition_hash
from modules.network.domain.release_contracts import canonical_hash, classify_contract_change, output_contract_snapshot, runtime_settings_hash
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database import schema_extensions  # install native metadata columns
from modules.agent.domain.release_versioning import calculate_next_release_version
from shared.contracts.errors import ConflictError


class NetworkASaCNativePublisher:
    async def capture(self, *, session, project_id, resource_id, candidate):
        source = await session.get(NetworkVersionModel, candidate.root_snapshot_id)
        if (source is None or source.project_id != project_id or source.network_id != resource_id
            or source.kind != "candidate"):
            raise ConflictError("ASAC_PUBLICATION_SOURCE_INVALID")
        if candidate.runtime_digest_scope != NETWORK_RUNTIME_SCOPE:
            raise ConflictError("ASAC_CANDIDATE_RUNTIME_SCOPE_INCOMPATIBLE: prepare a new Network Candidate with the advertised execution scope")
        parsed = NetworkDefinition.from_dict(source.definition)
        if (composition_hash(parsed, source.resolved_bindings) != source.composition_hash
            or network_runtime_digest(parsed, source.resolved_bindings, source.effective_external_context_contract) != candidate.runtime_digest
            or source.resolved_bindings != candidate.native_bindings):
            raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED")
        return {"snapshot_id": str(source.id), "definition": deepcopy(source.definition),
            "bindings": deepcopy(source.resolved_bindings), "contract": deepcopy(source.effective_external_context_contract),
            "native_composition_hash": source.composition_hash, "runtime_digest": candidate.runtime_digest,
            "runtime_digest_scope": NETWORK_RUNTIME_SCOPE, "record_digest": candidate.record_digest}

    async def publish(self, *, session, project_id, resource_id, candidate, principal, reason, source, children):
        current = await self.capture(session=session, project_id=project_id, resource_id=resource_id, candidate=candidate)
        if current != source:
            raise ConflictError("ASAC_PUBLICATION_SOURCE_INVALID: original preparation differs")
        definition, bindings = deepcopy(source["definition"]), deepcopy(source["bindings"])
        if set(children) != set(bindings):
            raise ConflictError("ASAC_PUBLICATION_PREPARATION_INCOMPLETE")
        manifest = []
        for node in definition["nodes"]:
            key, agent = str(node["id"]), str(node["agent_id"])
            receipt, binding = children[key], bindings[key]
            if (receipt["project_id"] != str(project_id) or receipt["resource_id"] != agent
                or receipt["source_snapshot_id"] != binding["release_id"]
                or receipt["runtime_digest"] != binding["runtime_digest"] or receipt["complete"] is not True):
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED: constituent copy proof differs")
            for field, value in binding["snapshot_override"].items():
                if field != "pinned_release_id" and receipt["release_snapshot"].get(field) != value:
                    raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED: executable override differs")
            node["binding"] = {"source": "release", "release_id": receipt["release_id"]}
            binding.update(release_id=receipt["release_id"], release_version=receipt["release_version"],
                release_status=receipt["release_status"], snapshot_kind="release", binding_source="release",
                snapshot_hash=receipt["runtime_digest"].removeprefix("sha256:"))
            if "pinned_release_id" in binding["snapshot_override"]:
                binding["snapshot_override"]["pinned_release_id"] = receipt["release_id"]
            manifest.append({"node_id": key, "agent_id": agent,
                "role": "entry" if key == str(definition["root_node_id"]) else "specialist",
                "release_id": receipt["release_id"], "release_version": receipt["release_version"],
                "snapshot_hash": receipt["runtime_digest"].removeprefix("sha256:"), "snapshot_schema_version": "2",
                "output_contract_hash": canonical_hash(output_contract_snapshot(SimpleNamespace(**receipt["release_snapshot"])))})
        parsed = NetworkDefinition.from_dict(definition)
        validate_network_environment_bindings(parsed, "production")
        runtime = network_runtime_digest(parsed, bindings, source["contract"])
        if runtime != candidate.runtime_digest:
            raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED: published executable closure differs")
        native_hash = composition_hash(parsed, bindings)
        releases = (await session.scalars(select(NetworkVersionModel).where(
            NetworkVersionModel.project_id == project_id, NetworkVersionModel.network_id == resource_id,
            NetworkVersionModel.kind == "release").order_by(NetworkVersionModel.created_at.desc(), NetworkVersionModel.id.desc()))).all()
        for released in releases:
            if (released.composition_hash == native_hash and released.definition == definition
                and released.resolved_bindings == bindings and released.effective_external_context_contract == source["contract"]):
                return {"release_id": released.id, "release_version": released.version, "reused": True,
                    "runtime_digest": runtime, "native_composition_hash": native_hash, "manifest": manifest}
        root = await session.get(NetworkModel, resource_id)
        previous = await session.get(NetworkVersionModel, root.production_version_id) if root.production_version_id else None
        entry_key = str(definition["root_node_id"])
        entry = children[entry_key]
        public_contract = output_contract_snapshot(SimpleNamespace(**entry["release_snapshot"]))
        change = strongest_release_change(classify_contract_change(getattr(previous, "public_output_contract", None), public_contract),
            classify_effective_external_context_change(getattr(previous, "effective_external_context_contract", None), source["contract"]))
        manifest.sort(key=lambda item: (item["role"] != "entry", item["node_id"]))
        native = NetworkVersionModel(id=uuid4(), project_id=project_id, network_id=resource_id,
            kind="release", version=calculate_next_release_version([row.version for row in releases], change),
            definition=definition, resolved_bindings=bindings, composition_hash=native_hash,
            effective_external_context_contract=source["contract"], created_by=getattr(principal, "user_id", None),
            source_version_id=candidate.root_snapshot_id, rollback_of_version_id=None,
            activation_kind=None, change_description=reason)
        native.entry_agent_id = UUID(bindings[entry_key]["agent_id"])
        native.entry_agent_release_id = UUID(entry["release_id"])
        native.entry_agent_release_version = entry["release_version"]
        native.public_output_contract, native.public_output_contract_hash = public_contract, canonical_hash(public_contract)
        native.agent_release_manifest, native.agent_release_manifest_hash = manifest, canonical_hash(manifest)
        native.runtime_settings_hash = runtime_settings_hash(parsed)
        native.release_fingerprint = canonical_hash({"composition_hash": native_hash,
            "public_output_contract_hash": native.public_output_contract_hash,
            "agent_release_manifest_hash": native.agent_release_manifest_hash,
            "runtime_settings_hash": native.runtime_settings_hash,
            "effective_external_context_contract": source["contract"]})
        native.change_kind = change.value
        session.add(native)
        await session.flush()
        return {"release_id": native.id, "release_version": native.version, "reused": False,
            "runtime_digest": runtime, "native_composition_hash": native_hash, "manifest": manifest}
