from uuid import UUID

from modules.network.application.dtos.management import (
    ActivateNetworkProductionInput,
    GetNetworkExecutionSnapshotInput,
    ListManagedNetworkVersionsInput,
    ListNetworkActivationsInput,
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


class ListManagedNetworkVersionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        versions = await self._use_case.execute(
            ListManagedNetworkVersionsInput(
                network_id=UUID(str(request.path_params["network_id"])),
                project_id=project_id,
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": [
                    {
                        **item.model_dump(exclude={"extensions"}),
                        **item.extensions,
                    }
                    for item in versions
                ],
            },
        )


class ListNetworkActivationsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        activations = await self._use_case.execute(
            ListNetworkActivationsInput(
                network_id=UUID(str(request.path_params["network_id"])),
                project_id=project_id,
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": [item.model_dump() for item in activations],
            },
        )


class GetNetworkExecutionSnapshotController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        snapshot = await self._use_case.execute(
            GetNetworkExecutionSnapshotInput(
                execution_id=UUID(str(request.path_params["execution_id"])),
                project_id=project_id,
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": snapshot},
        )


class ActivateNetworkProductionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        body = dict(request.body or {})
        result = await self._use_case.execute(
            ActivateNetworkProductionInput(
                network_id=UUID(str(request.path_params["network_id"])),
                project_id=project_id,
                source_version_id=UUID(str(body["source_version_id"])),
                expected_current_production_version_id=(
                    UUID(str(body["expected_current_production_version_id"]))
                    if body.get("expected_current_production_version_id")
                    else None
                ),
                change_description=str(body.get("change_description") or ""),
                created_by=actor_user_id(request),
            )
        )
        version_payload = {
            **result.version.model_dump(exclude={"extensions"}),
            **result.version.extensions,
        }
        return Response(
            status_code=201,
            body={
                "success": True,
                "data": {
                    "version": version_payload,
                    "activation": result.activation.model_dump(),
                },
            },
        )
