from __future__ import annotations

from modules.metering.application.dtos.project_usage import ProjectUsageQuery
from modules.metering.application.interfaces.use_case import UseCase
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class GetProjectUsageController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        allowed = {
            "from",
            "to",
            "bucket",
            "environment",
            "operation",
            "network_id",
            "agent_id",
            "provider_model_id",
            "release_id",
            "group_by",
            "top_limit",
        }
        query = ProjectUsageQuery.model_validate(
            {
                "project_id": request.path_params["project_id"],
                **{
                    key: value
                    for key, value in request.query_params.items()
                    if key in allowed
                },
            }
        )
        result = await self._use_case.execute(query)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": result.model_dump(by_alias=True, mode="json"),
            },
            headers={
                "Cache-Control": "private, max-age=15",
                "Vary": "Authorization",
            },
        )
