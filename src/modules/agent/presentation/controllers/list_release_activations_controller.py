from uuid import UUID

from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListAgentReleaseActivationsController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = UUID(request.path_params["agent_id"])
        items = await self._use_case.execute(agent_id)
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": [
                    {
                        "id": str(item.id),
                        "project_id": str(item.project_id),
                        "agent_id": str(item.agent_id),
                        "release_id": str(item.release_id),
                        "previous_release_id": str(item.previous_release_id) if item.previous_release_id else None,
                        "action": item.action,
                        "change_description": item.change_description,
                        "created_by": str(item.created_by) if item.created_by else None,
                        "created_at": item.created_at,
                    }
                    for item in items
                ],
            },
        )
