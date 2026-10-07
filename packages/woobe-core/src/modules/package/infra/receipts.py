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
    ):
        self.operation_id, self.lease_token, self.phase = (
            operation_id,
            lease_token,
            phase,
        )
        self.permission, self.encryption_key = permission, encryption_key
        self.evidence = evidence or {}
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
