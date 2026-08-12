from modules.billing.application.use_cases import CreateSubscriptionUseCase
from modules.billing.application.dtos import CreateSubscriptionInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateSubscriptionController(Controller):
    def __init__(self, use_case: CreateSubscriptionUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        input_dto = CreateSubscriptionInput(**request.body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={"success": True, "message": "created", "data": {"subscription_id": str(result.subscription_id)}},
        )
