from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from typing import Protocol

from modules.package.application.validation import validate_document
from modules.package.domain.bundle import PackageGraph
from modules.package.domain.errors import PackageError
from modules.package.domain.operations import Effect, OperationState


def definition_digest(value: dict) -> str:
    return sha256(
        b"woobe-package-definition@1.0\n"
        + json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


class NativePackageInspector(Protocol):
    """Owner validations only. Implementations must not materialize or invoke Models/Tools."""

    async def capabilities(self) -> dict: ...

    async def inspect_bindings(
        self, *, project_id, principal, requirements: dict, bindings: dict
    ) -> dict: ...

    async def inspect_component(
        self,
        *,
        project_id,
        principal,
        document: dict,
        graph: PackageGraph,
        support: Mapping[str, bytes],
        bindings: dict,
        inspected: dict,
    ) -> dict: ...

    async def authorize(
        self, *, project_id, principal, permissions: list[str]
    ) -> None: ...


@dataclass(frozen=True)
class ApprovedPlan:
    document: dict
    digest: str
    expires_at: datetime


def validate_binding_coverage(requirements: dict, bindings: dict) -> dict:
    validate_document(bindings, "import-bindings.yaml")
    if bindings["kind"] != "ImportBindings":
        raise PackageError("PACKAGE_BINDINGS_INVALID", "Expected ImportBindings")
    for group in ("credentials", "project_environment", "secrets", "knowledge"):
        field = "key" if group == "project_environment" else "ref"
        names = [entry[field] for entry in requirements.get(group, [])]
        if len(names) != len(set(names)):
            raise PackageError(
                "PACKAGE_REQUIREMENT_DUPLICATE", "Destination requirement is duplicated"
            )
    supplied = bindings["spec"]
    expected = {
        "credentials": {item["ref"] for item in requirements.get("credentials", [])},
        "project_environment": {
            item["key"] for item in requirements.get("project_environment", [])
        },
        "secrets": {item["ref"] for item in requirements.get("secrets", [])},
        "knowledge": {item["ref"] for item in requirements.get("knowledge", [])},
    }
    for group, aliases in expected.items():
        entries = supplied.get(group, {})
        if set(entries) != aliases:
            raise PackageError(
                "PACKAGE_BINDINGS_INCOMPLETE",
                "Bindings must match the declared destination requirements",
                path=f"/spec/{group}",
            )
    return supplied


class PlanPackageUseCase:
    def __init__(self, inspector: NativePackageInspector, *, lifetime_seconds=900):
        self._inspector, self._lifetime = inspector, lifetime_seconds

    async def execute(
        self,
        *,
        project_id,
        principal,
        graph: PackageGraph,
        support: Mapping[str, bytes],
        artifact_digest: str,
        upload_id,
        bindings: dict,
        lifecycle="draft",
        release_notes=None,
        reason=None,
        api_origin: str,
        candidate=None,
    ) -> ApprovedPlan:
        if lifecycle not in {"draft", "staging", "release", "production"}:
            raise PackageError(
                "PACKAGE_LIFECYCLE_INVALID", "Unknown requested lifecycle"
            )
        if lifecycle in {"release", "production"} and (
            not isinstance(release_notes, str) or not release_notes.strip()
        ):
            raise PackageError(
                "PACKAGE_RELEASE_NOTES_REQUIRED", "Release notes are required"
            )
        if lifecycle == "production" and (
            not isinstance(reason, str) or not reason.strip()
        ):
            raise PackageError(
                "PACKAGE_PRODUCTION_REASON_REQUIRED",
                "Production activation requires a reason",
            )
        requirements = graph.manifest["spec"].get("requires", {})
        supplied = validate_binding_coverage(requirements, bindings)
        capability = await self._inspector.capabilities()
        resolutions = await self._inspector.inspect_bindings(
            project_id=project_id,
            principal=principal,
            requirements=requirements,
            bindings=supplied,
        )
        inspected, effects = {}, []

        def append(
            key,
            action,
            component,
            permission,
            state=OperationState.MATERIALIZING,
            owner="agent",
        ):
            effects.append(
                Effect(key, owner, action, component, permission, state).public()
            )

        for group, permission, action in (
            ("credentials", "provider:write", "create_credential"),
            (
                "project_environment",
                "project:environment:write",
                "create_environment_value",
            ),
            ("secrets", "secret:write", "create_secret"),
        ):
            for alias in sorted(supplied.get(group, {})):
                if supplied[group][alias].get("protected_ref"):
                    append(
                        f"binding:{group}:{alias}",
                        action,
                        alias,
                        permission,
                        owner="core" if group == "project_environment" else "agent",
                    )
        for key in graph.order:
            document = graph.components[key]
            inspection = await self._inspector.inspect_component(
                project_id=project_id,
                principal=principal,
                document=document,
                graph=graph,
                support=support,
                bindings=resolutions,
                inspected=inspected,
            )
            inspected[key] = inspection
            kind = document["kind"]
            if kind == "Model":
                append(f"model:{key}", "resolve_model", key, "model:write")
            elif kind == "Tool":
                append(f"tool:{key}", "materialize_tool", key, "tool:write")
                if document["spec"]["type"] == "mcp":
                    append(f"mcp:{key}", "verify_mcp_discovery", key, "tool:write")
                    append(
                        f"mcp-ready:{key}", "verify_mcp_readiness", key, "tool:write"
                    )
            elif kind == "Skill":
                append(f"skill:{key}", "materialize_skill_version", key, "skill:write")
            elif kind == "Knowledge" and document["spec"]["mode"] == "portable":
                append(f"collection:{key}", "create_collection", key, "knowledge:write")
                for index, _ in enumerate(document["spec"]["documents"]):
                    append(
                        f"document:{key}:{index}",
                        "upload_document",
                        key,
                        "knowledge:write",
                    )
                append(f"vector:{key}", "build_vector_snapshot", key, "knowledge:write")
                append(
                    f"vector-ready:{key}",
                    "verify_vector_snapshot",
                    key,
                    "knowledge:read",
                )
            elif kind == "Agent":
                append(f"agent:{key}", "prepare_inactive_agent", key, "agent:write")
                for field, action, permission in (
                    ("prompt_ref", "create_prompt_version", "agent:version"),
                ):
                    if document["spec"].get(field):
                        append(f"prompt:{key}", action, key, permission)
                if (document["spec"].get("output") or {}).get("contract_ref"):
                    append(
                        f"contract:{key}",
                        "create_contract_version",
                        key,
                        "agent:version",
                    )
                if document["spec"].get("knowledge"):
                    append(
                        f"knowledge-version:{key}",
                        "create_agent_knowledge_version",
                        key,
                        "knowledge:write",
                    )
                append(f"draft:{key}", "finalize_agent_draft", key, "agent:version")
                effects[-1]["required_permissions"] = ["agent:version", "agent:write"]
            elif kind == "Network":
                selectors = {}
                for node in document["spec"]["nodes"]:
                    source = node.get("binding", {}).get("source", "draft")
                    previous = selectors.get(node["agent_ref"], "draft")
                    selectors[node["agent_ref"]] = (
                        "release"
                        if "release" in {source, previous}
                        else "staging"
                        if "staging" in {source, previous}
                        else "draft"
                    )
                for agent_key, source in sorted(selectors.items()):
                    if source != "draft":
                        append(
                            f"node-staging:{key}:{agent_key}",
                            "create_staging",
                            agent_key,
                            "agent:version",
                        )
                    if source == "release":
                        append(
                            f"node-release:{key}:{agent_key}",
                            "create_immutable_release",
                            agent_key,
                            "agent:version",
                        )
                append(
                    f"network:{key}",
                    "prepare_network",
                    key,
                    "network:write",
                    owner="network",
                )
                append(
                    f"network-draft:{key}",
                    "save_network_draft",
                    key,
                    "network:write",
                    owner="network",
                )

        entry = graph.manifest["spec"]["entrypoint"]
        # A Network freezes its own Agent bindings. It never promotes constituent
        # Agents to standalone Production as an incidental import effect.
        if lifecycle != "draft":
            owner, permission = (
                entry["kind"].lower(),
                f"{entry['kind'].lower()}:version",
            )
            append(
                f"staging:{entry['ref']}",
                "create_staging",
                entry["ref"],
                permission,
                owner=owner,
            )
            if owner == "network":
                effects[-1]["required_permissions"] = [
                    "network:version",
                    "agent:version",
                ]
            if lifecycle in {"release", "production"}:
                append(
                    f"release:{entry['ref']}",
                    "create_immutable_release",
                    entry["ref"],
                    permission,
                    owner=owner,
                )
            if lifecycle == "production":
                append(
                    f"production:{entry['ref']}",
                    "activate_production",
                    entry["ref"],
                    f"{owner}:production",
                    owner=owner,
                )
        if entry["kind"] == "Network":
            for agent_key in graph.order:
                if graph.components[agent_key]["kind"] == "Agent":
                    append(
                        f"agent-verification:{agent_key}",
                        "verify_constituent_agent",
                        agent_key,
                        "agent:read",
                        OperationState.VERIFYING,
                        owner="agent",
                    )
        append(
            "verification",
            "verify_materialized_package",
            entry["ref"],
            "project:read",
            OperationState.VERIFYING,
            owner="package",
        )
        permissions = sorted(
            {
                permission
                for effect in effects
                for permission in effect.get(
                    "required_permissions", [effect["permission"]]
                )
            }
            | {"project:read"}
        )
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self._lifetime)
        document = {
            "package_schema_version": "1.0",
            "api_origin": api_origin,
            "project_id": str(project_id),
            "upload_id": str(upload_id),
            "artifact_digest": artifact_digest,
            "definition_digest": definition_digest(
                {"manifest": graph.manifest, "components": graph.components}
            ),
            "capabilities_digest": definition_digest(capability),
            "bindings_digest": definition_digest(bindings),
            "bindings": bindings,
            "binding_resolutions": resolutions,
            "inspections": inspected,
            "source_definition": {
                "manifest": graph.manifest,
                "components": graph.components,
                "paths": graph.paths,
                "order": list(graph.order),
            },
            "lifecycle": lifecycle,
            "release_notes": release_notes,
            "reason": reason,
            "effects": effects,
            "required_permissions": permissions,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        if candidate is not None:
            from modules.package.application.candidate_planning import isolate_candidate_plan
            document = isolate_candidate_plan(document, **candidate)
        await self._inspector.authorize(project_id=project_id, principal=principal,
            permissions=document["required_permissions"])
        return ApprovedPlan(document, definition_digest(document), expires_at)
