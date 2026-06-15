from modules.core.application.use_cases import CreateProjectUseCase
from modules.core.application.dtos import CreateProjectInput
from modules.core.presentation.schemas import ProjectResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateProjectController(Controller):
    def __init__(self, use_case: CreateProjectUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateProjectInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": ProjectResponse(**result.model_dump()).model_dump()},
        )
