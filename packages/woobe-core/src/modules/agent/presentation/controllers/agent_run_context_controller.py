from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.agent_run_context import AgentRunContextUseCase
from shared.contracts.errors import AuthorizationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal


class AgentRunContextController:
    def __init__(self, use_case: AgentRunContextUseCase) -> None:
        self._use_case = use_case

    @staticmethod
    def _actor(request: OperationRequest) -> tuple[UUID | None, bool]:
        principal = request.principal
        if isinstance(principal, AuthenticatedPrincipal):
            return principal.user_id, False
        if isinstance(principal, ControlPlanePrincipal):
            return None, True
        raise AuthorizationError("Control-plane authentication required")

    async def handle_by_run(self, request: OperationRequest) -> OperationResult:
        user_id, control_plane_authorized = self._actor(request)
        data = await self._use_case.by_run(
            run_id=UUID(str(request.path_params["run_id"])),
            user_id=user_id,
            control_plane_authorized=control_plane_authorized,
        )
        return OperationResult(outcome=OperationOutcome.SUCCESS, body={"success": True, "data": data})

    async def handle_by_trace(self, request: OperationRequest) -> OperationResult:
        user_id, control_plane_authorized = self._actor(request)
        data = await self._use_case.by_trace(
            trace_id=UUID(str(request.path_params["trace_id"])),
            user_id=user_id,
            control_plane_authorized=control_plane_authorized,
        )
        return OperationResult(outcome=OperationOutcome.SUCCESS, body={"success": True, "data": data})

    async def handle_detail_by_run(self, request: OperationRequest) -> OperationResult:
        user_id, control_plane_authorized = self._actor(request)
        data = await self._use_case.detail_by_run(
            run_id=UUID(str(request.path_params["run_id"])),
            user_id=user_id,
            control_plane_authorized=control_plane_authorized,
        )
        return OperationResult(outcome=OperationOutcome.SUCCESS, body={"success": True, "data": data})

    async def handle_detail_by_trace(self, request: OperationRequest) -> OperationResult:
        user_id, control_plane_authorized = self._actor(request)
        data = await self._use_case.detail_by_trace(
            trace_id=UUID(str(request.path_params["trace_id"])),
            user_id=user_id,
            control_plane_authorized=control_plane_authorized,
        )
        return OperationResult(outcome=OperationOutcome.SUCCESS, body={"success": True, "data": data})

