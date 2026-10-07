"""Package phase dispatch through public owner composition boundaries."""

import asyncio
import posixpath
from hashlib import sha256
import json
from pathlib import PurePosixPath
from uuid import UUID

from modules.agent.contract_boundary import (
    compile_imported_agent_inputs,
    inspect_portable_skill,
    portable_skill_identity,
    ImportedDependencyPending,
    compile_imported_tool_inputs,
)
from modules.agent.entrypoint import (
    promote_release_composer,
    create_agent_composer,
    prepare_existing_agent_composer,
    reuse_frozen_agent_composer,
    reuse_development_resource_composer,
    verify_imported_agent_composer,
    create_contract_version_composer,
    create_prompt_version_composer,
    materialize_development_prompt_composer,
    materialize_development_contract_composer,
    materialize_development_collection_composer,
    materialize_development_document_composer,
    create_development_vector_composer,
    find_development_document_composer,
    finalize_existing_agent_composer,
    verify_development_agent_composer,
    create_provider_credential_composer,
    create_secret_composer,
    create_collection_composer,
    create_knowledge_version_composer,
    skill_catalog_composer,
    build_imported_document_preparation,
    upload_document_composer,
    create_imported_vector_composer,
    verify_imported_vector_composer,
    build_imported_mcp_preparation,
    commit_imported_mcp_composer,
    finalize_imported_agent_composer,
    materialize_imported_tool_composer,
    resolve_imported_model_composer,
)
from modules.package.domain.errors import PackageError
from modules.package.application.execution import DependencyWait
from modules.core.entrypoint import create_imported_environment_composer
from modules.network.entrypoint import imported_network_composer
from modules.package.domain.bundle import portable_path
from modules.package.infra.receipts import PackageTransactionReceipt
from shared.presentation.contracts import OperationRequest


def result_data(result):
    body = result.body
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise PackageError(
            "PACKAGE_NATIVE_EVIDENCE_INVALID", "Native phase has no resource evidence"
        )
    return body["data"]


def installed_resources(work):
    resources = {}
    for phase, response in work.receipts.items():
        data = result_data(response)
        resources[phase] = data
        group, _, key = phase.partition(":")
        if group in {"model", "tool", "skill", "agent", "network", "vector-ready"}:
            resources[key] = data
    for key, component in work.plan["source_definition"]["components"].items():
        if component["kind"] == "Knowledge" and component["spec"]["mode"] == "binding":
            resources[key] = work.plan["binding_resolutions"]["knowledge"][
                component["spec"]["binding"]["ref"]
            ]
    return resources


class NativePackageMaterializer:
    def __init__(self, *, encryption_key, artifacts=None):
        self._encryption_key = encryption_key
        self._artifacts = artifacts

    def _skill_input(self, work, key, document):
        if self._artifacts is None:
            raise PackageError(
                "PACKAGE_ARTIFACT_UNAVAILABLE", "Artifact reader is unavailable"
            )
        with self._artifacts.capture_record(work.upload) as bundle:
            spec = document["spec"]
            descriptor = work.plan["source_definition"]["paths"][key]
            manifest = portable_path(spec["package"]["manifest"], descriptor=descriptor)
            resources = {}
            for path in spec["package"].get("resources", []):
                absolute = portable_path(path, descriptor=descriptor)
                relative = posixpath.relpath(
                    absolute, posixpath.dirname(manifest) or "."
                )
                resources[relative] = (bundle.root / absolute).read_text(
                    encoding="utf-8"
                )
            incoming = {
                "version": spec["version"],
                "skill_md": (bundle.root / manifest).read_text(encoding="utf-8"),
                "resources": resources,
                "required_tools": spec.get("required_tools", []),
            }
            if (
                portable_skill_identity(inspect_portable_skill(**incoming))
                != work.plan["inspections"][key]
            ):
                raise PackageError(
                    "PACKAGE_ARTIFACT_CHANGED",
                    "Skill differs from its approved definition",
                )
            return incoming

    def _document_bytes(self, work, key, document, index):
        if self._artifacts is None:
            raise PackageError(
                "PACKAGE_ARTIFACT_UNAVAILABLE", "Artifact reader is unavailable"
            )
        path = portable_path(
            document["spec"]["documents"][index]["path"],
            descriptor=work.plan["source_definition"]["paths"][key],
        )
        with self._artifacts.capture_record(work.upload) as bundle:
            return (bundle.root / path).read_bytes()

    async def execute_phase(self, work, phase):
        operation = work.operation
        key, action = phase["component"], phase["action"]
        definitions = work.plan["source_definition"]["components"]
        resources = installed_resources(work)
        document = definitions.get(key)
        inspection = work.plan["inspections"].get(key, {})
        project = str(operation.project_id)
        paths = {"project_id": project}
        metadata = {"required_permission": phase["permission"]}
        target = work.plan.get("resource_bindings", {}).get(key, {})
        if (
            target.get("resource_id")
            and target.get("kind") == "Agent"
            and not target.get("frozen")
            and action
            in {"prepare_existing_agent", "finalize_agent_draft", "reuse_resource"}
        ):
            metadata["expected_agent_revision"] = str(target["evidence"]["revision"])
        if action == "reuse_frozen_snapshot":
            paths["agent_id"] = target["resource_id"]
            body = {
                "project_id": project,
                "agent_id": target["resource_id"],
                "release_id": target["evidence"]["snapshot_id"],
                "snapshot_digest": target["evidence"]["snapshot_digest"],
            }
            handler = reuse_frozen_agent_composer()
        elif action == "reuse_resource":
            body = {
                "project_id": project,
                "kind": target["kind"],
                "resource_id": target["resource_id"],
                "expected_revision": target["evidence"]["revision"],
            }
            parameter = {
                "Agent": "agent_id",
                "Tool": "tool_id",
                "Model": "provider_model_id",
                "Skill": "skill_version_id",
                "Knowledge": "snapshot_id",
            }[target["kind"]]
            paths[parameter] = target["resource_id"]
            handler = reuse_development_resource_composer()
        elif action == "prepare_existing_agent":
            body = {"project_id": project}
            paths["agent_id"] = target["resource_id"]
            handler = prepare_existing_agent_composer()
        elif action == "create_credential":
            requirement = next(
                item
                for item in work.plan["source_definition"]["manifest"]["spec"][
                    "requires"
                ]["credentials"]
                if item["ref"] == key
            )
            reference = work.plan["bindings"]["spec"]["credentials"][key][
                "protected_ref"
            ]
            body = {
                "project_id": project,
                "provider": requirement["provider"],
                "name": key,
                "secret": work.payload["protected_bindings"][reference],
                "metadata": requirement.get("metadata"),
            }
            handler = create_provider_credential_composer()
        elif action == "create_environment_value":
            requirement = next(
                item
                for item in work.plan["source_definition"]["manifest"]["spec"][
                    "requires"
                ]["project_environment"]
                if item["key"] == key
            )
            reference = work.plan["bindings"]["spec"]["project_environment"][key][
                "protected_ref"
            ]
            body = {
                "project_id": project,
                "key": key,
                "kind": requirement["kind"],
                "value": work.payload["protected_bindings"][reference],
            }
            handler = create_imported_environment_composer()
        elif action == "create_secret":
            reference = work.plan["bindings"]["spec"]["secrets"][key]["protected_ref"]
            body = {
                "project_id": project,
                "name": key,
                "value": work.payload["protected_bindings"][reference],
            }
            handler = create_secret_composer()
        elif action == "materialize_skill_version":
            body = await asyncio.to_thread(self._skill_input, work, key, document)
            metadata["skill_operation"] = "resolve_import"
            if work.plan.get("mode") == "sync":
                metadata["skill_operation"] = "resolve_development_import"
                if skill_id := (target.get("evidence") or {}).get("skill_id"):
                    paths["skill_id"] = skill_id
            handler = skill_catalog_composer()
        elif action == "create_collection":
            body = {"project_id": project, **document["spec"]["collection"]}
            if work.plan.get("mode") == "sync":
                body["development_collection_id"] = (target.get("evidence") or {}).get(
                    "collection_id"
                )
                handler = materialize_development_collection_composer()
            else:
                handler = create_collection_composer()
        elif action == "upload_document":
            index = int(phase["key"].rsplit(":", 1)[1])
            descriptor = document["spec"]["documents"][index]
            content = await asyncio.to_thread(
                self._document_bytes, work, key, document, index
            )
            preparation = build_imported_document_preparation()
            inputs = dict(
                project_id=operation.project_id,
                collection_id=UUID(resources["collection:" + key]["id"]),
                file_name=PurePosixPath(descriptor["path"]).name,
                title=descriptor["title"],
                content=content,
                content_type=descriptor.get("content_type"),
            )
            existing = None
            if work.plan.get("mode") == "sync":
                candidate = preparation.inspect(**inputs)
                lookup = await find_development_document_composer()(
                    OperationRequest(principal=work.principal, body=candidate)
                )
                existing = lookup.body.get("data")
            body = candidate if existing else await preparation.execute(**inputs)
            handler = (
                materialize_development_document_composer()
                if work.plan.get("mode") == "sync"
                else upload_document_composer()
            )
        elif action == "build_vector_snapshot":
            embedding = resources[document["spec"]["embedding"]["model_ref"]]
            body = {
                "project_id": project,
                "collection_id": resources["collection:" + key]["id"],
                "embedding_provider_model_id": embedding["id"],
                "build_config": document["spec"]["vector_snapshot"],
                "document_ids": [
                    resources[f"document:{key}:{index}"]["id"]
                    for index, _ in enumerate(document["spec"]["documents"])
                ],
            }
            if work.plan.get("mode") == "sync":
                identity = {**body, "document_ids": sorted(body["document_ids"])}
                body["version"] = sha256(
                    json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                handler = create_development_vector_composer()
            else:
                handler = create_imported_vector_composer()
        elif action == "verify_vector_snapshot":
            body = {
                "project_id": project,
                "snapshot_id": resources["vector:" + key]["id"],
            }
            handler = verify_imported_vector_composer()
        elif action == "create_agent_knowledge_version":
            source = resources[document["spec"]["knowledge"]["source"]["ref"]]
            agent_id = resources[key]["id"]
            body = {
                "project_id": project,
                "agent_id": agent_id,
                "collection_ids": [source["collection_id"]],
                "snapshot_metadata": {
                    "vector_snapshot_id": source.get(
                        "vector_snapshot_id", source.get("id")
                    )
                },
            }
            paths["agent_id"] = agent_id
            handler = create_knowledge_version_composer()
        elif action == "resolve_model":
            alias = document["spec"]["credential"]["ref"]
            resolution = work.plan["binding_resolutions"]["credentials"][alias]
            credential = (
                resolution.get("credential_id")
                or resources[f"binding:credentials:{alias}"]["id"]
            )
            body = {
                "project_id": project,
                "provider_credential_id": credential,
                "name": document["metadata"]["name"],
                "model": inspection["model"],
                "model_type": inspection["model_type"],
                "spec": inspection["spec"],
                "metadata": {"base_url": document["spec"]["base_url"]}
                if document["spec"].get("base_url")
                else {},
                "expected_spec_hash": inspection["spec_hash"],
                "expected_credential_revision": inspection.get("credential_revision"),
                "expected_model_id": inspection.get("existing_model_id"),
                "expected_model_revision": inspection.get("model_revision"),
            }
            handler = resolve_imported_model_composer()
        elif action == "materialize_tool":
            environment = {
                alias: (binding.get("existing_key") or alias)
                for alias, binding in work.plan["bindings"]["spec"]
                .get("project_environment", {})
                .items()
            }
            secrets = {
                alias: (binding.get("existing_key") or alias)
                for alias, binding in work.plan["bindings"]["spec"]
                .get("secrets", {})
                .items()
            }
            body = compile_imported_tool_inputs(
                project_id=operation.project_id,
                metadata=document["metadata"],
                spec=document["spec"],
                environment=environment,
                secrets=secrets,
            )
            if work.plan.get("mode") == "sync" and target.get("evidence", {}).get(
                "owner_agent_id"
            ):
                body["agent_id"] = target["evidence"]["owner_agent_id"]
            handler = materialize_imported_tool_composer()
        elif action in {"verify_mcp_discovery", "verify_mcp_readiness"}:
            environment = {
                alias: (binding.get("existing_key") or alias)
                for alias, binding in work.plan["bindings"]["spec"]
                .get("project_environment", {})
                .items()
            }
            tool_id = UUID(resources[key]["id"])
            try:
                body = await build_imported_mcp_preparation().execute(
                    project_id=operation.project_id,
                    principal=work.principal,
                    tool_id=tool_id,
                    desired_permissions=[
                        {
                            **item,
                            "bindings": {
                                name: {
                                    "source": {
                                        **binding["source"],
                                        "field": environment[binding["source"]["field"]]
                                        if binding["source"]["kind"]
                                        == "project_environment"
                                        else binding["source"]["field"],
                                    }
                                }
                                for name, binding in item.get("bindings", {}).items()
                            },
                        }
                        for item in document["spec"].get("permissions", [])
                    ],
                    require_ready=action == "verify_mcp_readiness",
                )
            except ImportedDependencyPending as pending:
                return DependencyWait(pending.dependencies)
            paths["tool_id"] = str(tool_id)
            handler = commit_imported_mcp_composer()
        elif action == "prepare_inactive_agent":
            body = compile_imported_agent_inputs(
                resolve_skill_versions=work.plan.get("mode") == "sync",
                project_id=operation.project_id,
                document=document,
                definitions=definitions,
                resources=resources,
            )
            handler = create_agent_composer()
        elif action in {"create_prompt_version", "create_contract_version"}:
            agent_id = resources[key]["id"]
            reference = (
                document["spec"]["prompt_ref"]
                if action == "create_prompt_version"
                else document["spec"]["output"]["contract_ref"]
            )
            body = {
                **work.plan["inspections"][reference],
                "project_id": project,
                "agent_id": agent_id,
            }
            paths["agent_id"] = agent_id
            handler = (
                (
                    materialize_development_prompt_composer()
                    if action == "create_prompt_version"
                    else materialize_development_contract_composer()
                )
                if work.plan.get("mode") == "sync"
                else (
                    create_prompt_version_composer()
                    if action == "create_prompt_version"
                    else create_contract_version_composer()
                )
            )
        elif action == "finalize_agent_draft":
            agent_id = resources[key]["id"]
            body = compile_imported_agent_inputs(
                resolve_skill_versions=work.plan.get("mode") == "sync",
                project_id=operation.project_id,
                document=document,
                definitions=definitions,
                resources=resources,
                agent_id=UUID(agent_id),
                release_notes=work.plan["release_notes"],
            )
            paths["agent_id"] = agent_id
            handler = (
                finalize_existing_agent_composer()
                if target.get("resource_id")
                and not target.get("preparation", {}).get("new_root")
                else finalize_imported_agent_composer()
            )
        elif (
            document
            and document["kind"] == "Agent"
            and action
            in {"create_staging", "create_immutable_release", "activate_production"}
        ):
            if phase["key"].startswith("node-staging:"):
                source_key = "draft:" + key
            elif phase["key"].startswith("node-release:"):
                source_key = phase["key"].replace("node-release:", "node-staging:", 1)
            else:
                source_key = {
                    "create_staging": "draft:",
                    "create_immutable_release": "staging:",
                    "activate_production": "release:",
                }[action] + key
            paths.update(
                agent_id=resources[key]["id"], release_id=resources[source_key]["id"]
            )
            body = {
                "target_status": {
                    "create_staging": "staging",
                    "create_immutable_release": "released",
                    "activate_production": "production",
                }[action],
                "release_notes": work.plan["release_notes"],
                "change_description": work.plan["reason"],
            }
            handler = promote_release_composer()
        elif document and document["kind"] == "Network":
            body = {
                "project_id": project,
                "action": action,
                "name": document["metadata"]["name"],
                "description": document["metadata"].get("description", ""),
                "release_notes": work.plan["release_notes"],
                "activation_reason": work.plan["reason"],
                "lifecycle": work.plan["lifecycle"],
            }
            if action == "prepare_network" and target.get("resource_id"):
                body.update(
                    network_id=target["resource_id"],
                    expected_revision=target["evidence"]["revision"],
                )
                paths["network_id"] = target["resource_id"]
            if action != "prepare_network":
                body["network_id"] = resources[key]["id"]
                paths["network_id"] = body["network_id"]
                body["expected_revision"] = resources.get(
                    "network-draft:" + key, resources[key]
                )["revision"]
            if action in {"save_network_draft", "verify_materialized_package"}:
                body["portable_spec"] = document["spec"]
                body["agents"] = {
                    node["agent_ref"]: resources[node["agent_ref"]]["id"]
                    for node in document["spec"]["nodes"]
                }
                body["snapshots"] = {}
                for agent_key in body["agents"]:
                    body["snapshots"][agent_key] = {
                        source: resources[prefix + key + ":" + agent_key]["id"]
                        for source, prefix in (
                            ("staging", "node-staging:"),
                            ("release", "node-release:"),
                        )
                        if prefix + key + ":" + agent_key in resources
                    }
            if action == "create_immutable_release":
                body["source_version_id"] = resources["staging:" + key]["id"]
            elif action == "activate_production" or (
                action == "verify_materialized_package"
                and work.plan["lifecycle"] in {"release", "production"}
            ):
                body["source_version_id"] = resources["release:" + key]["id"]
            elif (
                action == "verify_materialized_package"
                and work.plan["lifecycle"] == "staging"
            ):
                body["source_version_id"] = resources["staging:" + key]["id"]
            handler = imported_network_composer()
        elif (
            action in {"verify_materialized_package", "verify_constituent_agent"}
            and document["kind"] == "Agent"
        ):
            body = {
                "project_id": project,
                "agent_id": resources[key]["id"],
                "draft_id": resources["draft:" + key]["id"],
                "lifecycle": "draft"
                if action == "verify_constituent_agent"
                else work.plan["lifecycle"],
                "release_id": resources.get(
                    ("staging:" if work.plan["lifecycle"] == "staging" else "release:")
                    + key,
                    {},
                ).get("id"),
            }
            handler = (
                verify_development_agent_composer()
                if work.plan.get("mode") == "sync"
                else verify_imported_agent_composer()
            )
        else:
            raise PackageError(
                "PACKAGE_NATIVE_PHASE_UNSUPPORTED",
                "Native phase composition is not implemented",
            )
        receipt = PackageTransactionReceipt(
            operation_id=operation.id,
            lease_token=operation.lease_token,
            phase=phase["key"],
            permission=phase["permission"],
            encryption_key=self._encryption_key,
            evidence={
                "component": key,
                "artifact_component": reference
                if action in {"create_prompt_version", "create_contract_version"}
                else None,
                "kind": document["kind"] if document else "Binding",
                "action": action,
            },
        )
        try:
            return await handler.with_receipt(receipt)(
                OperationRequest(
                    principal=work.principal,
                    path_params=paths,
                    body=body,
                    metadata=metadata,
                )
            )
        except ImportedDependencyPending as pending:
            return DependencyWait(pending.dependencies)
