from uuid import UUID

from modules.network.application.dtos.management import ListManagedNetworkVersionsInput
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    authorize_project,
    project_id_from_request,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ListLegacyNetworkVersionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        result = await self._use_case.execute(
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
                        "id": item.id,
                        "kind": item.kind,
                        "version": item.version,
                        "composition_hash": item.composition_hash,
                        "definition": item.definition,
                        "resolved_bindings": item.resolved_bindings,
                        "created_at": item.created_at,
                    }
                    for item in result
                ],
            },
        )
