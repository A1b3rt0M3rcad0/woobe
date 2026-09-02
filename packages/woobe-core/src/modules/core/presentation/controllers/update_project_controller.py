from modules.core.application.interfaces.use_case import UseCase
from modules.core.application.dtos import UpdateProjectInput
from modules.core.presentation.schemas import ProjectResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class UpdateProjectController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body)
        body["project_id"] = request.path_params["project_id"]
        input_dto = UpdateProjectInput(**body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": ProjectResponse(**result.model_dump()).model_dump()},
        )
