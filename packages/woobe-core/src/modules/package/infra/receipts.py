from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from modules.package.domain.errors import PackageError
from modules.package.domain.operations import OperationState
from modules.package.infra.models import PackageEffectModel, PackageOperationModel
from shared.infra.admin_idempotency import principal_identity
from shared.infra.crypto import decrypt_secret, encrypt_secret
from shared.presentation.contracts import OperationRequest, OperationResult
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer


async def authorize_phase(session, principal, project_id, permission):
    authorizer = TenantAuthorizer(session)
    workspace_id = await authorizer._project_workspace_id(project_id)
    if isinstance(principal, ControlPlanePrincipal):
        await authorizer.require_active_control(principal)
        await authorizer.authorize_control_key(
            api_key_id=principal.api_key_id,
            workspace_id=principal.workspace_id,
            workspace_permissions=principal.permissions,
            required_permission=permission,
            path_params={"project_id": str(project_id)},
            query_params={},
            body={},
        )
    elif isinstance(principal, AuthenticatedPrincipal):
        await authorizer.require_active_human(principal)
        await authorizer.require_human_permission(
            user_id=principal.user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            permission=permission,
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
        await authorize_phase(
            session, request.principal, operation.project_id, self.permission
        )
        if operation.lease_token != self.lease_token or operation.state not in {
            OperationState.RESOLVING,
            OperationState.MATERIALIZING,
            OperationState.VERIFYING,
        }:
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
        operation.phases_completed += 1
        operation.phase = self.phase
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
