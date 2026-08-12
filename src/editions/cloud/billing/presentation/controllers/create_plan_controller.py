from editions.cloud.billing.application.use_cases import CreatePlanUseCase
from editions.cloud.billing.application.dtos import CreatePlanInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreatePlanController(Controller):
    def __init__(self, use_case: CreatePlanUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreatePlanInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": {"plan_id": str(result.plan_id)}},
        )
