from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime

from modules.package.application.planning import PlanPackageUseCase, definition_digest
from modules.package.domain.bundle import PackageGraph, support_paths
from modules.package.domain.errors import PackageError
from modules.package.infra.models import PackagePlanModel, PackageUploadModel
from modules.package.infra.operation_repository import as_utc
from modules.package.infra.receipts import authorize_phase
from shared.infra.admin_idempotency import principal_identity


PUBLIC_PLAN_FIELDS = (
    "mode",
    "registry_id",
    "resource_bindings",
    "api_origin",
    "project_id",
    "upload_id",
    "artifact_digest",
    "definition_digest",
    "capabilities_digest",
    "bindings_digest",
    "bindings",
    "binding_resolutions",
    "lifecycle",
    "release_notes",
    "reason",
    "effects",
    "required_permissions",
    "created_at",
    "expires_at",
)


def plan_status(record):
    return {
        "package_schema_version": "1.0",
        "plan_id": str(record.id),
        "plan_digest": record.plan_digest,
        **{key: record.document.get(key) for key in PUBLIC_PLAN_FIELDS},
    }


class PackagePlanRepository:
    def __init__(self, session_factory, artifacts, inspector, registry=None):
        self.registry = registry
        self._sessions, self._artifacts, self._inspector = (
            session_factory,
            artifacts,
            inspector,
        )

    async def create(
        self,
        *,
        project_id,
        principal,
        upload_id,
        artifact_digest,
        bindings,
        lifecycle,
        release_notes,
        reason,
        api_origin,
        mode="create",
        registry_id=None,
        resource_bindings=None,
    ):
        upload = await self._artifacts.get_record(
            project_id=project_id, principal=principal, upload_id=upload_id
        )
        if upload.artifact_digest != artifact_digest:
            raise PackageError(
                "PACKAGE_ARTIFACT_CHANGED",
                "Uploaded package differs from the requested artifact",
            )
        bundle = await asyncio.to_thread(self._artifacts.capture_record, upload)
        try:
            support = CapturedSkillSupport(bundle)
            approved = await PlanPackageUseCase(self._inspector).execute(
                project_id=project_id,
                principal=principal,
                graph=bundle.graph,
                support=support,
                artifact_digest=artifact_digest,
                upload_id=upload_id,
                bindings=bindings,
                lifecycle=lifecycle,
                release_notes=release_notes,
                reason=reason,
                api_origin=api_origin,
            )
            if mode == "sync":
                if self.registry is None:
                    raise PackageError("PACKAGE_UNSUPPORTED", "Development registry is unavailable")
                async with self._sessions.begin() as session:
                    await self.registry.prepare(session, project_id=project_id, principal=principal, registry_id=registry_id, targets=resource_bindings, graph=bundle.graph, inventory=bundle.inventory, document=approved.document)
        finally:
            bundle.close()
        record = PackagePlanModel(
            project_id=project_id,
            actor=principal_identity(principal),
            upload_id=upload_id,
            artifact_digest=artifact_digest,
            plan_digest=definition_digest(approved.document),
            document=approved.document,
            expires_at=approved.expires_at,
        )
        async with self._sessions.begin() as session:
            current = await session.get(PackageUploadModel, upload_id)
            if current is None or as_utc(current.expires_at) <= datetime.now(UTC):
                raise PackageError(
                    "PACKAGE_UPLOAD_EXPIRED", "Uploaded package has expired"
                )
            for permission in approved.document["required_permissions"]:
                await authorize_phase(session, principal, project_id, permission)
            session.add(record)
            await session.flush()
        return plan_status(record)

    async def validate_acceptance(self, session, plan, payload, *, principal):
        # This callback runs inside the short acceptance transaction. It performs
        # only native read scopes and pure contract checks; it never opens storage,
        # uploads documents, invokes providers or discovers MCP servers.
        document = plan.document
        if self.registry and document.get("mode") == "sync":
            await self.registry.validate(session, plan, principal)
        if payload.get("bindings") != document["bindings"]:
            raise PackageError(
                "PACKAGE_PLAN_MISMATCH", "Bindings differ from the approved plan"
            )
        if any(
            payload.get(field) != document[field]
            for field in ("release_notes", "reason")
        ):
            raise PackageError(
                "PACKAGE_PLAN_MISMATCH",
                "Lifecycle audit fields differ from the approved plan",
            )
        required = {
            binding["protected_ref"]
            for group in document["bindings"]["spec"].values()
            for binding in group.values()
            if binding.get("protected_ref")
        }
        protected = payload.get("protected_bindings", {})
        if (
            not isinstance(protected, dict)
            or set(protected) != required
            or any(
                not isinstance(value, str) or not value for value in protected.values()
            )
        ):
            raise PackageError(
                "PACKAGE_PROTECTED_BINDINGS_INVALID",
                "Apply must resolve exactly its approved protected references",
            )
        if (
            definition_digest(await self._inspector.capabilities())
            != document["capabilities_digest"]
        ):
            raise PackageError(
                "PACKAGE_CAPABILITIES_CHANGED",
                "Server capabilities changed after planning",
            )
        source = document["source_definition"]
        graph = PackageGraph(
            source["manifest"],
            source["components"],
            source["paths"],
            tuple(source["order"]),
        )
        bindings = await self._inspector.inspect_bindings(
            project_id=plan.project_id,
            principal=principal,
            requirements=graph.manifest["spec"].get("requires", {}),
            bindings=document["bindings"]["spec"],
        )
        if bindings != document["binding_resolutions"]:
            raise PackageError(
                "PACKAGE_BINDINGS_CHANGED",
                "Destination bindings changed after planning",
            )
        inspected = dict(document["inspections"])
        for key in graph.order:
            if graph.components[key]["kind"] == "Model":
                inspected[key] = await self._inspector.inspect_component(
                    project_id=plan.project_id,
                    principal=principal,
                    document=graph.components[key],
                    graph=graph,
                    support={},
                    bindings=bindings,
                    inspected=inspected,
                )
        if inspected != document["inspections"]:
            raise PackageError(
                "PACKAGE_PRECONDITION_CHANGED",
                "Native resource definitions changed after planning",
            )


    async def reserve_development(self, session, plan, operation):
        if self.registry and plan.document.get("mode") == "sync":
            await self.registry.reserve(session, plan, operation)


class CapturedSkillSupport(Mapping):
    """Read only requested Skill files from the owned immutable capture."""

    def __init__(self, bundle):
        self._root = bundle.root
        self._paths = {
            path
            for key, component in bundle.graph.components.items()
            if component["kind"] == "Skill"
            for path in support_paths(component, bundle.graph.paths[key])
        }

    def __getitem__(self, path):
        if path not in self._paths:
            raise KeyError(path)
        return (self._root / path).read_bytes()

    def __len__(self):
        return len(self._paths)

    def __iter__(self):
        return iter(self._paths)
