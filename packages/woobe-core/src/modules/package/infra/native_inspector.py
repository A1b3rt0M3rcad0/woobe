from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from importlib.resources import files
import posixpath

from modules.agent.contract_boundary import (
    inspect_portable_agent,
    inspect_portable_agent_capabilities,
    inspect_portable_knowledge,
    inspect_portable_version_definition,
    portable_skill_identity,
    inspect_portable_network_external_context,
    inspect_portable_skill,
    inspect_proposed_provider_model,
    portable_definition_capabilities,
)
from modules.agent.entrypoint import (
    inspect_destination_bindings_composer,
    inspect_provider_model_definition_composer,
)
from modules.package.domain.bundle import portable_path
from modules.package.domain.errors import PackageError
from modules.package.infra.receipts import authorize_phase
from shared.presentation.contracts import OperationRequest
from shared.contracts.errors import ValidationError


from modules.agent.contract_boundary import compile_imported_tool_inputs


class NativePackageInspectorGateway:
    def __init__(self, session_factory, network_service):
        self._sessions, self._network = session_factory, network_service

    async def capabilities(self):
        catalog = (
            files("modules.package.domain.schemas")
            .joinpath("catalog.json")
            .read_bytes()
        )
        return {
            "package_schema_version": "1.0",
            # Git may check this text resource out with CRLF on Windows. The
            # compatibility contract hashes LF bytes, matching the pinned CLI
            # catalog; line endings do not change the schema itself.
            "schema_catalog_sha256": sha256(catalog.replace(b"\r\n", b"\n")).hexdigest(),
            "agent": portable_definition_capabilities(),
            "network": self._network.package_capabilities(),
        }

    async def authorize(self, *, project_id, principal, permissions):
        async with self._sessions() as session:
            for permission in sorted(set(permissions)):
                await authorize_phase(session, principal, project_id, permission)

    async def inspect_bindings(self, *, project_id, principal, requirements, bindings):
        reads = ["project:read"]
        for group, permission in (
            ("credentials", "provider:read"),
            ("secrets", "secret:read"),
            ("project_environment", "project:environment:read"),
            ("knowledge", "knowledge:read"),
        ):
            if bindings.get(group):
                reads.append(permission)
        await self.authorize(
            project_id=project_id, principal=principal, permissions=reads
        )
        providers = {
            item["ref"]: item["provider"]
            for item in requirements.get("credentials", [])
        }
        credential_metadata = {
            item["ref"]: item.get("metadata")
            for item in requirements.get("credentials", [])
        }
        environment_kinds = {
            item["key"]: item["kind"]
            for item in requirements.get("project_environment", [])
        }
        body = {
            "project_id": str(project_id),
            **bindings,
            "credentials": {
                alias: {
                    **value,
                    "provider": providers[alias],
                    "metadata": credential_metadata[alias],
                }
                for alias, value in bindings.get("credentials", {}).items()
            },
            "project_environment": {
                alias: {**value, "kind": environment_kinds[alias]}
                for alias, value in bindings.get("project_environment", {}).items()
            },
        }
        result = await inspect_destination_bindings_composer()(
            OperationRequest(
                principal=principal,
                body=body,
                path_params={"project_id": str(project_id)},
            )
        )
        return result.body["data"]

    async def inspect_component(
        self, *, project_id, principal, document, graph, support, bindings, inspected
    ):
        document = deepcopy(document)
        kind, spec = document["kind"], document["spec"]
        key, metadata = document["metadata"]["key"], document["metadata"]
        permission = {
            "Model": "model:read",
            "Agent": "agent:read",
            "Network": "network:read",
            "Tool": "tool:read",
            "Skill": "skill:read",
            "Knowledge": "knowledge:read",
            "Contract": "agent:read",
            "Prompt": "agent:read",
        }[kind]
        await self.authorize(
            project_id=project_id, principal=principal, permissions=[permission]
        )
        try:
            if kind == "Model":
                credential = bindings["credentials"][spec["credential"]["ref"]]
                if credential.get("credential_id"):
                    body = {
                        "project_id": str(project_id),
                        "provider_credential_id": credential["credential_id"],
                        "name": metadata["name"],
                        "model": spec["model"],
                        "model_type": spec.get("model_type", "language"),
                        "spec": spec.get("model_spec_hint"),
                        "metadata": {"base_url": spec["base_url"]}
                        if spec.get("base_url")
                        else {},
                    }
                    result = await inspect_provider_model_definition_composer()(
                        OperationRequest(
                            principal=principal,
                            body=body,
                            path_params={"project_id": str(project_id)},
                            metadata={"required_permission": "model:read"},
                        )
                    )
                    definition = result.body["data"]
                else:
                    definition = inspect_proposed_provider_model(
                        project_id=project_id, metadata=metadata, spec=spec
                    )
                return {**definition, "base_url": spec.get("base_url")}
            if kind == "Tool":
                create = compile_imported_tool_inputs(
                    project_id=project_id,
                    metadata=metadata,
                    spec=spec,
                    environment={
                        alias: alias
                        for alias in bindings.get("project_environment", {})
                    },
                    secrets={alias: alias for alias in bindings.get("secrets", {})},
                )
                return {
                    "create_input": create,
                    "binding_permission": spec.get("permission", "allow"),
                    "mcp_permissions": spec.get("permissions", []),
                }
            if kind == "Skill":
                descriptor = graph.paths[key]
                manifest = portable_path(
                    spec["package"]["manifest"], descriptor=descriptor
                )
                resources = {
                    posixpath.relpath(
                        portable_path(path, descriptor=descriptor),
                        posixpath.dirname(manifest) or ".",
                    ): support[portable_path(path, descriptor=descriptor)].decode(
                        "utf-8"
                    )
                    for path in spec["package"].get("resources", [])
                }
                package = inspect_portable_skill(
                    version=spec["version"],
                    skill_md=support[manifest].decode("utf-8"),
                    resources=resources,
                    required_tools=spec.get("required_tools", []),
                )
                return portable_skill_identity(package)
            if kind == "Agent":
                models = [
                    inspected[spec["model"][role]["ref"]]["spec"]
                    for role in ("primary", "fallback")
                    if spec["model"].get(role)
                ]
                result = inspect_portable_agent(spec, model_specs=models)
                tools = {
                    item["ref"]: inspected[item["ref"]]
                    for item in spec.get("tools", [])
                }
                skills = {
                    item["ref"]: inspected[item["ref"]]
                    for item in spec.get("skills", [])
                }
                result.update(
                    inspect_portable_agent_capabilities(
                        spec=spec, tools=tools, skills=skills
                    )
                )
                output = spec.get("output") or {}
                if output.get("contract_ref"):
                    contract = graph.components[output["contract_ref"]]["spec"][
                        "output_schema"
                    ]
                    inline = output.get("output_schema")
                    response = output.get("response_format") or {}
                    if (inline is not None and inline != contract) or (
                        response.get("schema") is not None
                        and response["schema"] != contract
                    ):
                        raise PackageError(
                            "PACKAGE_CONTRACT_MISMATCH",
                            "Inline output differs from its referenced Contract",
                        )
                return result
            if kind == "Network":
                result = self._network.inspect_portable_definition(spec)
                contracts = {
                    node["key"]: inspected[node["agent_ref"]][
                        "external_context_contract"
                    ]
                    for node in spec["nodes"]
                }
                return {
                    **result,
                    "external_context_contract": inspect_portable_network_external_context(
                        contracts
                    ),
                }
            if kind == "Knowledge":
                if spec["mode"] == "binding":
                    return bindings["knowledge"][spec["binding"]["ref"]]
                return inspect_portable_knowledge(
                    spec=spec,
                    embedding_spec=inspected[spec["embedding"]["model_ref"]]["spec"],
                )
            if kind in {"Prompt", "Contract"}:
                return inspect_portable_version_definition(
                    kind=kind, metadata=metadata, spec=spec
                )
        except PackageError:
            raise
        except (ValueError, ValidationError) as exc:
            raise PackageError(
                "PACKAGE_NATIVE_VALIDATION_FAILED",
                "Owning domain rejected the portable definition",
                file=graph.paths[key],
                path="/spec",
            ) from exc
        raise PackageError(
            "PACKAGE_SCHEMA_UNSUPPORTED", "No native inspection contract for this kind"
        )
