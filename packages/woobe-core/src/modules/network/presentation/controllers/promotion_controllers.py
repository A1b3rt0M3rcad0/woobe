from uuid import UUID

from modules.network.application.dtos.promotion import (
    PromoteNetworkInput,
    PreviewNetworkPromotionInput,
)
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    actor_user_id,
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class PreviewNetworkPromotionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            PreviewNetworkPromotionInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                environment=body.get("environment", "staging"),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": result},
        )


class PromoteNetworkController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            PromoteNetworkInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                environment=body.get("environment", "staging"),
                created_by=actor_user_id(request),
                expected_revision=body.get("expected_revision"),
                expected_network_version_id=body.get("expected_network_version_id"),
                approved_action_ids=body.get("approved_action_ids") or [],
            )
        )
        return Response(
            status_code=201,
            body={
                "success": True,
                "data": {
                    "id": result.id,
                    "kind": result.kind,
                    "version": result.version,
                    "composition_hash": result.composition_hash,
                    "definition": result.definition,
                    "resolved_bindings": result.resolved_bindings,
                },
            },
        )
