from __future__ import annotations

from modules.core.application.dtos.project_overview import ProjectOverviewQuery
from modules.core.application.use_cases.get_project_overview import (
    GetProjectOverviewUseCase,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class GetProjectOverviewController(Controller):
    def __init__(self, use_case: GetProjectOverviewUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        raw_query = {
            "project_id": request.path_params["project_id"],
            **{
                key: value
                for key, value in request.query_params.items()
                if key in {"from", "to", "bucket", "environment", "recent_limit"}
            },
        }
        query = ProjectOverviewQuery.model_validate(raw_query)
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
