from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from modules.package.domain.errors import PackageError
from modules.package.domain.operations import OperationState
from modules.package.infra.models import (
    PackageEffectModel,
    PackageOperationModel,
    PackagePlanModel,
    PackageResourceBindingModel,
)
from shared.infra.admin_idempotency import principal_identity
from shared.infra.crypto import decrypt_secret, encrypt_secret
from shared.presentation.contracts import OperationRequest, OperationResult
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer


async def authorize_phase(
    session,
    principal,
    project_id,
    permission,
    *,
    path_params=None,
    query_params=None,
    body=None,
):
    authorizer = TenantAuthorizer(session)
    workspace_id = await authorizer._project_workspace_id(project_id)
    if isinstance(principal, ControlPlanePrincipal):
        await authorizer.require_active_control(principal)
        await authorizer.authorize_control_key(
            api_key_id=principal.api_key_id,
            workspace_id=principal.workspace_id,
            workspace_permissions=principal.permissions,
            required_permission=permission,
            path_params={"project_id": str(project_id), **(path_params or {})},
            query_params=query_params or {},
            body=body or {},
        )
    elif isinstance(principal, AuthenticatedPrincipal):
        await authorizer.require_active_human(principal)
        await authorizer.require_human_permission(
            user_id=principal.user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            permission=permission,
            path_context={"project_id": str(project_id), **(path_params or {})},
        )
    else:
        raise PackageError(
            "PACKAGE_AUTHORITY_REQUIRED", "Administrative authentication is required"
        )


class PackageTransactionReceipt:
    """A phase receipt commits in the same transaction as its domain mutation.

    The operation row is a fence: an expired worker cannot append effects after
    another worker claims the operation, or after cancellation is requested.
    """

    def __init__(
        self,
        *,
        operation_id: UUID,
        lease_token: UUID,
        phase: str,
        permission: str,
        encryption_key: str,
        evidence: dict | None = None,
        binding_reader=None,
    ):
        self.operation_id, self.lease_token, self.phase = (
            operation_id,
            lease_token,
            phase,
        )
        self.permission, self.encryption_key = permission, encryption_key
        self.evidence = evidence or {}
        self.binding_reader = binding_reader
        self.operation = None

    async def lookup(self, uow, request: OperationRequest) -> OperationResult | None:
        session = uow.session
        operation = (
            await session.execute(
                select(PackageOperationModel)
                .where(PackageOperationModel.id == self.operation_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if operation is None or operation.actor != principal_identity(
            request.principal
        ):
            raise PackageError(
                "PACKAGE_OPERATION_NOT_FOUND", "Operation is unavailable"
            )
        paths = request.metadata.get("authorization_path_params", request.path_params)
        body = request.body if isinstance(request.body, dict) else {}
        supplied_projects = [
            value
            for value in (paths.get("project_id"), body.get("project_id"))
            if value is not None
        ]
        if not supplied_projects or any(
            str(value) != str(operation.project_id) for value in supplied_projects
        ):
            raise PackageError(
                "PACKAGE_PROJECT_MISMATCH",
                "Phase does not belong to the accepted project",
            )
        plan = await session.get(PackagePlanModel, operation.plan_id)
        approved = (
            next(
                (
                    effect
                    for effect in plan.document["effects"]
                    if effect["key"] == self.phase
                ),
                None,
            )
            if plan
            else None
        )
        if approved is None or approved["permission"] != self.permission:
            raise PackageError(
                "PACKAGE_PHASE_NOT_APPROVED", "Phase is absent from the accepted plan"
            )
        for permission in sorted(
            set(approved.get("required_permissions", [self.permission]))
            | {self.permission}
        ):
            await authorize_phase(
                session,
                request.principal,
                operation.project_id,
                permission,
                path_params=paths,
                query_params=request.query_params,
                body=request.body,
            )
        lease_expired = operation.lease_until is None or operation.lease_until.replace(
            tzinfo=operation.lease_until.tzinfo or UTC
        ) <= datetime.now(UTC)
        if (
            lease_expired
            or operation.lease_token != self.lease_token
            or operation.state
            not in {
                OperationState.RESOLVING,
                OperationState.MATERIALIZING,
                OperationState.VERIFYING,
            }
        ):
            raise PackageError(
                "PACKAGE_OPERATION_FENCED",
                "Operation no longer accepts this worker's effects",
            )
        self.operation = operation
        record = (
            await session.execute(
                select(PackageEffectModel).where(
                    PackageEffectModel.operation_id == self.operation_id,
                    PackageEffectModel.phase == self.phase,
                )
            )
        ).scalar_one_or_none()
        if record is not None:
            return OperationResult.model_validate_json(
                decrypt_secret(record.response_ciphertext, self.encryption_key)
            )
        return None

    async def save(self, uow, request, response: OperationResult):
        if response.outcome.value not in {"success", "created", "accepted"}:
            raise PackageError(
                "PACKAGE_DOMAIN_REJECTED", "Owning domain rejected this import phase"
            )
        if self.operation is None:
            raise RuntimeError("A phase must reserve its receipt before recording it")
        uow.session.add(
            PackageEffectModel(
                operation_id=self.operation_id,
                phase=self.phase,
                response_ciphertext=encrypt_secret(
                    response.model_dump_json(), self.encryption_key
                ),
            )
        )
        operation = self.operation
        plan = await uow.session.get(PackagePlanModel, operation.plan_id)
        target = (
            plan.document.get("resource_bindings", {}).get(
                self.evidence.get("artifact_component")
                or self.evidence.get("component")
            )
            if plan
            else None
        )
        completed_actions = {
            "Agent": {
                "finalize_agent_draft",
                "reuse_resource",
                "reuse_frozen_snapshot",
            },
            "Network": {"save_network_draft"},
            "Model": {"resolve_model", "reuse_resource"},
            "Tool": {"materialize_tool", "reuse_resource"},
            "Skill": {"materialize_skill_version", "reuse_resource"},
            "Knowledge": {"verify_vector_snapshot", "reuse_resource"},
        }
        completed_actions.update(
            Prompt={"create_prompt_version"}, Contract={"create_contract_version"}
        )
        preparing = self.evidence.get("action") in {
            "prepare_inactive_agent",
            "prepare_existing_agent",
            "prepare_network",
        }
        auxiliary = (
            target
            and target["kind"] == "Knowledge"
            and self.evidence.get("action") == "create_collection"
        )
        if target and (
            auxiliary
            or preparing
            or self.evidence.get("action")
            in completed_actions.get(target["kind"], set())
        ):
            binding = await uow.session.scalar(
                select(PackageResourceBindingModel)
                .where(
                    PackageResourceBindingModel.project_id == operation.project_id,
                    PackageResourceBindingModel.registry_id
                    == UUID(plan.document["registry_id"]),
                    PackageResourceBindingModel.resource_uid
                    == UUID(target["resource_uid"]),
                )
                .with_for_update()
            )
            if binding is None or binding.operation_id != operation.id:
                raise PackageError(
                    "PACKAGE_REGISTRY_CONFLICT",
                    "Resource binding no longer belongs to this operation",
                )
            data = response.body.get("data", {})
            identifier = (
                (data.get("agent_id") or data.get("id"))
                if target["kind"] == "Agent"
                else data.get("vector_snapshot_id", data.get("id"))
            )
            if not identifier:
                raise PackageError(
                    "PACKAGE_NATIVE_EVIDENCE_INVALID",
                    "Resource binding has no native identity",
                )
            if auxiliary:
                binding.preparation = {
                    **(binding.preparation or {}),
                    "collection_id": str(identifier),
                }
            else:
                binding.resource_id = UUID(str(identifier))
                binding.definition_digest = (
                    None if preparing else target["definition_digest"]
                )
                if preparing:
                    binding.preparation = {
                        **(binding.preparation or {}),
                        "new_root": target.get("preparation", {}).get("new_root")
                        or target.get("resource_id") is None,
                        "root_revision": data.get("revision", 1),
                    }
                else:
                    # This evidence belongs to this exact accepted phase, not a
                    # later GET of a resource that another writer can mutate.
                    await uow.session.flush()
                    accepted = None
                    if target.get("frozen"):
                        accepted = target.get("evidence")
                    elif self.binding_reader is not None:
                        accepted = await self.binding_reader(
                            uow.session, project_id=operation.project_id,
                            principal=request.principal, kind=target["kind"],
                            resource_id=binding.resource_id, lock=True,
                        )
                    preparation = dict(binding.preparation or {})
                    preparation.pop("root_revision", None)
                    preparation.pop("new_root", None)
                    # Never carry evidence from an older phase forward when this
                    # writer cannot provide a new accepted generation.
                    preparation.pop("accepted_native", None)
                    if accepted and accepted.get("revision") is not None:
                        preparation["accepted_native"] = {
                            "revision": accepted["revision"],
                            "resource_id": str(binding.resource_id),
                            "operation_id": str(operation.id),
                            "definition_digest": target["definition_digest"],
                            "frozen": bool(target.get("frozen")),
                            "snapshot_id": accepted.get("snapshot_id"),
                        }
                    binding.preparation = preparation
        operation.dependencies = []
        operation.phases_completed += 1
        operation.phase = self.phase
        if self.phase == "verification":
            data = (
                response.body.get("data", {}) if isinstance(response.body, dict) else {}
            )
            if data.get("configuration_ready") is not True:
                raise PackageError(
                    "PACKAGE_OPERATION_INCOMPLETE",
                    "Native verifier has not established configuration readiness",
                )
            operation.configuration_ready = True
            operation.execution_ready = data.get("execution_ready") is True
            operation.lifecycle_state = data.get("lifecycle_state")
        operation.revision += 1
        if self.evidence:
            evidence = dict(self.evidence)
            body = response.body if isinstance(response.body, dict) else {}
            resource = body.get("data", body)
            if isinstance(resource, dict) and resource.get("id"):
                evidence["resource_id"] = str(resource["id"])
            # Evidence is constructed by server composition; never copy whole DTOs.
            operation.inventory = [*operation.inventory, evidence]
        await uow.session.flush()
