from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

from shared.contracts.unit_of_work import UnitOfWork
from shared.contracts.transaction_receipt import TransactionReceipt


RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")

Handler = Callable[[RequestT], Awaitable[ResponseT]]


class TransactionalHandler(Generic[RequestT, ResponseT]):
    def __init__(
        self,
        uow: UnitOfWork,
        handler: Handler[RequestT, ResponseT],
        *, guarded: bool = True,
    ) -> None:
        self._uow = uow
        self._handler = handler
        self._guarded = guarded

    def with_receipt(
        self, receipt: TransactionReceipt[RequestT, ResponseT]
    ) -> "TransactionalHandler[RequestT, ResponseT]":
        async def recorded(request: RequestT) -> ResponseT:
            replay = await receipt.lookup(self._uow, request)
            if replay is not None:
                return replay
            result = await self._invoke(request)
            await receipt.save(self._uow, request, result)
            return result

        return TransactionalHandler(self._uow, recorded, guarded=False)

    async def _invoke(self, request: RequestT) -> ResponseT:
        guard = getattr(self._uow, "validate_revision", None)
        if self._guarded and guard is not None:
            await guard(request)
        return await self._handler(request)

    async def __call__(self, request: RequestT) -> ResponseT:
        async with self._uow:
            from shared.presentation.contracts import OperationRequest, OperationResult
            from shared.security.principal import ControlPlanePrincipal
            from sqlalchemy.ext.asyncio import AsyncSession

            if isinstance(request, OperationRequest) and isinstance(
                request.principal, ControlPlanePrincipal
            ):
                from shared.security.tenancy import TenantAuthorizer

                session = getattr(self._uow, "session", None)
                if isinstance(session, AsyncSession):
                    authorizer = TenantAuthorizer(session)
                    await authorizer.require_active_control(request.principal)
                    if request.metadata.get("required_permission"):
                        await authorizer.authorize_control_key(
                            api_key_id=request.principal.api_key_id,
                            workspace_id=request.principal.workspace_id,
                            workspace_permissions=request.principal.permissions,
                            required_permission=request.metadata["required_permission"],
                            path_params=request.metadata.get(
                                "authorization_path_params", request.path_params
                            ),
                            query_params=request.query_params,
                            body=request.body,
                        )
            if isinstance(request, OperationRequest) and request.metadata.get(
                "idempotency_key"
            ):
                from sqlalchemy.ext.asyncio import AsyncSession
                from shared.infra.admin_idempotency import AdministrativeIdempotency
                from shared.infra.config import Settings
                from shared.security.tenancy import TenantAuthorizer
                from shared.security.principal import ControlPlanePrincipal
                from shared.contracts.errors import ValidationError

                session = getattr(self._uow, "session", None)
                if not isinstance(session, AsyncSession):
                    raise ValidationError("This operation does not support idempotency")
                workspace_id = (
                    request.body.get("workspace_id")
                    if isinstance(request.body, dict)
                    else None
                )
                project_id = request.path_params.get("project_id") or (
                    request.body.get("project_id")
                    if isinstance(request.body, dict)
                    else None
                )
                from uuid import UUID

                if project_id:
                    workspace_id = await TenantAuthorizer(
                        session
                    )._project_workspace_id(UUID(str(project_id)))
                if workspace_id is None and isinstance(
                    request.principal, ControlPlanePrincipal
                ):
                    workspace_id = request.principal.workspace_id
                if workspace_id is None or request.principal is None:
                    raise ValidationError(
                        "Idempotency requires authenticated Workspace context"
                    )
                ledger = AdministrativeIdempotency(
                    session, encryption_key=Settings.model_validate({}).encryption_key
                )
                replay = await ledger.begin(
                    key=request.metadata["idempotency_key"],
                    actor=request.principal,
                    workspace_id=UUID(str(workspace_id)),
                    operation=request.metadata["operation_name"],
                    payload={
                        "body": request.body,
                        "path": request.path_params,
                        "query": request.query_params,
                    },
                )
                if replay is not None:
                    result = OperationResult.model_validate(replay["result"])
                    result.metadata["Idempotency-Replayed"] = "true"
                    return result
                result = await self._invoke(request)
                if isinstance(result, OperationResult) and result.outcome.value in {
                    "success",
                    "created",
                    "accepted",
                }:
                    await ledger.save({"result": result.model_dump(mode="json")})
                elif ledger.record is not None:
                    await session.delete(ledger.record)
                return result
            return await self._invoke(request)
