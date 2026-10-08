"""Package-owned identities; resource inspection stays behind owner gateways."""

from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, text

from modules.package.application.planning import definition_digest
from modules.package.application.semantic_definition import semantic_digests
from shared.infra.admin_idempotency import principal_identity
from modules.package.domain.bundle import component_references, support_paths
from modules.package.domain.errors import PackageError
from modules.package.domain.operations import TERMINAL_STATES
from modules.package.infra.models import (
    PackageOperationModel,
    PackageResourceBindingModel,
    PackageExportModel,
)
from modules.package.infra.receipts import authorize_phase


class DevelopmentRegistry:
    def __init__(self, sessions, agent_reader, network_reader):
        self._sessions = sessions
        self._readers = {
            kind: agent_reader
            for kind in (
                "Agent",
                "Model",
                "Tool",
                "Skill",
                "Knowledge",
                "Prompt",
                "Contract",
            )
        }
        self._readers["Network"] = network_reader

    async def inspect(
        self, session, *, project_id, principal, kind, resource_id, lock=False
    ):
        return await self._readers[kind].inspect(
            session,
            project_id=project_id,
            principal=principal,
            kind=kind,
            resource_id=resource_id,
            lock=lock,
        )

    async def bindings(self, *, project_id, principal, registry_id):
        async with self._sessions() as session:
            if session.bind.dialect.name == "postgresql":
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                )
            await authorize_phase(session, principal, project_id, "project:read")
            rows = (
                await session.scalars(
                    select(PackageResourceBindingModel)
                    .where(
                        PackageResourceBindingModel.project_id == project_id,
                        PackageResourceBindingModel.registry_id == registry_id,
                    )
                    .order_by(PackageResourceBindingModel.resource_uid)
                )
            ).all()
            result = []
            for row in rows:
                evidence = None
                if row.resource_id is not None and row.kind in self._readers:
                    evidence = await self.inspect(
                        session,
                        project_id=project_id,
                        principal=principal,
                        kind=row.kind,
                        resource_id=row.resource_id,
                    )
                accepted = (row.preparation or {}).get("accepted_native")
                unfinished = False
                if accepted and (
                    accepted.get("operation_id") != str(row.operation_id)
                    or accepted.get("definition_digest") != row.definition_digest
                    or accepted.get("resource_id") != str(row.resource_id)
                ):
                    operation = (
                        await session.get(PackageOperationModel, row.operation_id)
                        if row.operation_id
                        else None
                    )
                    if operation and operation.state != "succeeded":
                        # A new operation has reserved/prepared this binding but
                        # has not accepted its new definition. Do not combine its
                        # current native ID/generation with the prior receipt.
                        accepted, unfinished = None, True
                    else:
                        raise PackageError(
                            "PACKAGE_NATIVE_EVIDENCE_INVALID",
                            "Accepted generation belongs to another binding receipt",
                        )
                if not accepted and not unfinished and row.operation_id:
                    operation = await session.get(
                        PackageOperationModel, row.operation_id
                    )
                    unfinished = bool(operation and operation.state != "succeeded")
                current = evidence["revision"] if evidence else None
                result.append(
                    {
                        "resource_uid": str(row.resource_uid),
                        "kind": row.kind,
                        "resource_id": str(row.resource_id)
                        if row.resource_id
                        else None,
                        "definition_digest": row.definition_digest,
                        "operation_id": str(row.operation_id)
                        if row.operation_id
                        else None,
                        "revision": accepted["revision"]
                        if accepted
                        else None
                        if unfinished
                        else current,
                        "accepted_revision": accepted["revision"] if accepted else None,
                        "current_revision": current,
                        "generation_scope": "unsealed_native_binding"
                        if unfinished
                        else "accepted_native_phase"
                        if accepted
                        else "legacy_current_observation",
                        "binding_status": (
                            "frozen_snapshot"
                            if accepted.get("frozen")
                            else "unchanged"
                            if str(accepted["revision"]) == str(current)
                            else "resource_changed"
                        )
                        if accepted
                        else "binding_incomplete"
                        if unfinished
                        else "accepted_generation_unavailable",
                        "frozen": bool(accepted and accepted.get("frozen")),
                        "snapshot_id": accepted.get("snapshot_id")
                        if accepted
                        else None,
                        "identifiers": {
                            field: evidence[field]
                            for field in ("skill_id", "collection_id")
                            if evidence and evidence.get(field)
                        },
                    }
                )
            return {
                "package_schema_version": "1.0",
                "registry_id": str(registry_id),
                "resources": result,
            }

    async def prepare(
        self,
        session,
        *,
        project_id,
        principal,
        registry_id,
        targets,
        graph,
        inventory,
        document,
    ):
        if set(targets) != set(graph.components):
            raise PackageError(
                "PACKAGE_REGISTRY_INVALID",
                "Synchronization must identify every declared component exactly once",
            )
        uids = [target["resource_uid"] for target in targets.values()]
        if len(set(uids)) != len(uids):
            raise PackageError(
                "PACKAGE_REGISTRY_INVALID",
                "A resource UID cannot identify multiple package components",
            )
        semantic = semantic_digests(
            graph.components,
            graph.order,
            graph.paths,
            inventory,
            {
                alias: value["credential_id"]
                for alias, value in document["binding_resolutions"]
                .get("credentials", {})
                .items()
            },
        )
        digests, prepared = {}, {}
        files = {item["path"]: item for item in inventory}
        for key in graph.order:
            component = graph.components[key]
            kind, target = component["kind"], targets[key]
            supports = [
                files[path] for path in support_paths(component, graph.paths[key])
            ]
            digests[key] = definition_digest(
                {
                    "component": component,
                    "dependencies": {
                        ref: digests[ref]
                        for ref, _, _ in component_references(component)
                    },
                    "support": supports,
                    "bindings": document["bindings"],
                }
            )
            row = await session.scalar(
                select(PackageResourceBindingModel).where(
                    PackageResourceBindingModel.project_id == project_id,
                    PackageResourceBindingModel.registry_id == UUID(registry_id),
                    PackageResourceBindingModel.resource_uid
                    == UUID(target["resource_uid"]),
                )
            )
            resource_id = target.get("resource_id")
            if row is not None:
                if row.kind != kind or (
                    resource_id and str(row.resource_id) != resource_id
                ):
                    raise PackageError(
                        "PACKAGE_REGISTRY_CONFLICT",
                        "Resource identity differs from its registered binding",
                    )
                resource_id = str(row.resource_id) if row.resource_id else None
            evidence = None
            if resource_id:
                if kind not in self._readers:
                    raise PackageError(
                        "PACKAGE_REGISTRY_INVALID",
                        "This component has no independent native identity",
                    )
                evidence = await self.inspect(
                    session,
                    project_id=project_id,
                    principal=principal,
                    kind=kind,
                    resource_id=resource_id,
                )
                expected = target.get("expected_revision")
                if (
                    row is not None
                    and row.definition_digest is None
                    and row.preparation.get("root_revision") is not None
                    and str(evidence["revision"])
                    != str(row.preparation["root_revision"])
                ):
                    raise PackageError(
                        "PACKAGE_REVISION_CONFLICT",
                        "Prepared resource was changed by another client; pull it before resuming",
                    )
                if target.get("release_id") is None and (
                    expected is None or str(expected) != str(evidence["revision"])
                ):
                    raise PackageError(
                        "PACKAGE_REVISION_CONFLICT",
                        "Resource changed after the local base was observed",
                    )
            if (
                kind == "Knowledge"
                and row is not None
                and row.preparation.get("collection_id")
            ):
                evidence = {
                    **(evidence or {}),
                    "collection_id": row.preparation["collection_id"],
                }
            frozen = target.get("release_id") is not None
            source = None
            original = None
            if target.get("source_export_id") and target.get("source_component"):
                source = await session.get(
                    PackageExportModel, UUID(target["source_export_id"])
                )
                if (
                    source is not None
                    and source.project_id == project_id
                    and source.actor == principal_identity(principal)
                ):
                    original = source.source.get("resource_bindings", {}).get(
                        target["source_component"]
                    )
                else:
                    source = None
            captured_unchanged = bool(
                evidence
                and original
                and source
                and original.get("resource_id") == resource_id
                and str(original.get("revision")) == str(evidence["revision"])
                and source.source.get("semantic_digests", {}).get(
                    target["source_component"]
                )
                == semantic[key]
                and (
                    kind in {"Skill", "Knowledge"}
                    or (kind == "Tool" and original.get("native_matches"))
                    or (
                        kind == "Agent"
                        and original.get("source_kind") == "draft"
                        and not original.get("frozen")
                    )
                )
            )
            if frozen:
                if (
                    kind != "Agent"
                    or not resource_id
                    or not target.get("source_export_id")
                    or not target.get("source_component")
                ):
                    raise PackageError(
                        "PACKAGE_REGISTRY_INVALID",
                        "Frozen reuse requires its original authorized export evidence",
                    )
                source = await session.get(
                    PackageExportModel, UUID(target["source_export_id"])
                )
                original = (
                    source.source.get("resource_bindings", {}).get(
                        target["source_component"]
                    )
                    if source
                    else None
                )
                if (
                    source is None
                    or source.project_id != project_id
                    or source.actor != principal_identity(principal)
                ):
                    raise PackageError(
                        "PACKAGE_FROZEN_RESOURCE_CHANGED",
                        "Frozen constituent source export is unavailable",
                        path="/source_export_id",
                    )
                if (
                    not original
                    or not original.get("frozen")
                    or original.get("resource_id") != resource_id
                    or original.get("snapshot_id") != target["release_id"]
                ):
                    raise PackageError(
                        "PACKAGE_FROZEN_RESOURCE_CHANGED",
                        "Frozen constituent identity differs from its source",
                        path="/release_id",
                    )
                if (
                    source.source.get("semantic_digests", {}).get(
                        target["source_component"]
                    )
                    != semantic[key]
                ):
                    raise PackageError(
                        "PACKAGE_FROZEN_RESOURCE_CHANGED",
                        "Frozen Network constituent definition changed; edit the Agent Draft or clone it explicitly",
                        path="/definition_digest",
                    )
                evidence["snapshot_id"] = target["release_id"]
                evidence["source_kind"] = original["source_kind"]
                evidence["snapshot_digest"] = original["snapshot_digest"]
            prepared[key] = {
                **target,
                "frozen": frozen,
                "kind": kind,
                "resource_id": resource_id,
                "definition_digest": digests[key],
                "evidence": evidence,
                "preparation": row.preparation if row is not None else {},
                "unchanged": captured_unchanged
                or bool(row and evidence and row.definition_digest == digests[key]),
            }
        document.update(
            mode="sync", registry_id=registry_id, resource_bindings=prepared
        )
        # Native mutable roots retain identity. Dependency changes are explicit
        # copy-on-write effects; immutable versions never rewrite old consumers.
        reuse_actions = {
            "Tool": "materialize_tool",
            "Skill": "materialize_skill_version",
            "Knowledge": "verify_vector_snapshot",
            "Agent": "finalize_agent_draft",
        }
        filtered = []
        for effect in document["effects"]:
            target = prepared.get(effect["component"])
            if target is None:
                filtered.append(effect)
                continue
            kind, action = target["kind"], effect["action"]
            if target.get("frozen"):
                if action in {
                    "create_prompt_version",
                    "create_contract_version",
                    "create_agent_knowledge_version",
                }:
                    continue
                if action in {
                    "finalize_agent_draft",
                    "create_staging",
                    "create_immutable_release",
                    "verify_constituent_agent",
                }:
                    effect = {**effect, "action": "reuse_frozen_snapshot"}
                    filtered.append(effect)
                    continue
            if target["unchanged"] and kind in reuse_actions:
                if kind == "Tool" and action in {
                    "verify_mcp_discovery",
                    "verify_mcp_readiness",
                }:
                    # Rediscovery writes timestamps and increments the native
                    # Tool revision, invalidating unchanged Agent Draft snapshots.
                    # Reuse checks its approved revision; final owner verification
                    # still checks exact snapshots and persisted MCP readiness.
                    continue
                if kind == "Knowledge" and action in {
                    "create_collection",
                    "upload_document",
                    "build_vector_snapshot",
                }:
                    continue
                if kind == "Agent" and action in {
                    "create_prompt_version",
                    "create_contract_version",
                    "create_agent_knowledge_version",
                }:
                    continue
                if action == reuse_actions[kind]:
                    effect = {
                        **effect,
                        "action": "reuse_resource",
                        "required_permissions": [effect["permission"]],
                    }
            if target["resource_id"] and action == "prepare_inactive_agent":
                effect = {**effect, "action": "prepare_existing_agent"}
            if (
                target["resource_id"]
                and kind not in {"Agent", "Network"}
                and not target["unchanged"]
            ):
                effect = {**effect, "identity_policy": "copy_on_write"}
            filtered.append(effect)
        document["effects"] = filtered

    async def validate(self, session, plan, principal):
        for target in plan.document.get("resource_bindings", {}).values():
            if target.get("resource_id"):
                observed = await self.inspect(
                    session,
                    project_id=plan.project_id,
                    principal=principal,
                    kind=target["kind"],
                    resource_id=target["resource_id"],
                    lock=True,
                )
                if not target.get("frozen") and str(observed["revision"]) != str(
                    target["evidence"]["revision"]
                ):
                    raise PackageError(
                        "PACKAGE_REVISION_CONFLICT",
                        "Resource changed after synchronization planning",
                    )

    async def reserve(self, session, plan, operation):
        for target in sorted(
            plan.document.get("resource_bindings", {}).values(),
            key=lambda value: value["resource_uid"],
        ):
            identity = (
                operation.project_id,
                UUID(plan.document["registry_id"]),
                UUID(target["resource_uid"]),
            )
            if session.bind.dialect.name == "postgresql":
                lock = int.from_bytes(
                    sha256(str(identity).encode()).digest()[:8], "big", signed=True
                )
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock}
                )
            row = await session.scalar(
                select(PackageResourceBindingModel)
                .where(
                    PackageResourceBindingModel.project_id == identity[0],
                    PackageResourceBindingModel.registry_id == identity[1],
                    PackageResourceBindingModel.resource_uid == identity[2],
                )
                .with_for_update()
            )
            if row is None:
                row = PackageResourceBindingModel(
                    project_id=identity[0],
                    registry_id=identity[1],
                    resource_uid=identity[2],
                    kind=target["kind"],
                    resource_id=UUID(target["resource_id"])
                    if target["resource_id"]
                    else None,
                )
                session.add(row)
            else:
                if row.kind != target["kind"] or str(row.resource_id or "") != str(
                    target["resource_id"] or ""
                ):
                    raise PackageError(
                        "PACKAGE_REGISTRY_CONFLICT",
                        "Registry binding changed after planning",
                    )
                if row.operation_id:
                    prior = await session.get(PackageOperationModel, row.operation_id)
                    if prior and prior.state not in TERMINAL_STATES:
                        raise PackageError(
                            "PACKAGE_REGISTRY_CONFLICT",
                            "Another operation owns this resource binding",
                        )
            row.operation_id = operation.id
        await session.flush()
