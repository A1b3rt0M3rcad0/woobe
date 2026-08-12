from editions.cloud.billing.application.use_cases import GetOrganizationSubscriptionUseCase
from editions.cloud.billing.application.dtos import GetOrganizationSubscriptionInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetOrganizationSubscriptionController(Controller):
    def __init__(self, use_case: GetOrganizationSubscriptionUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        org_id = request.path_params["org_id"]
        input_dto = GetOrganizationSubscriptionInput(organization_id=org_id)
        result = await self._use_case.execute(input_dto)
        if result is None:
            return Response(
                status_code=404,
                body={"success": False, "message": "Subscription not found", "data": None},
            )
        return Response(
            status_code=200,
            body={"success": True, "message": "ok", "data": result.model_dump()},
        )
