from modules.core.application.use_cases import CreateApiKeyUseCase
from modules.core.application.dtos import CreateApiKeyInput
from modules.core.presentation.schemas import ApiKeyResponse
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateApiKeyController(Controller):
    def __init__(self, use_case: CreateApiKeyUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        body = dict(request.body)
        body["project_id"] = request.path_params["project_id"]
        body["created_by_user_id"] = request.user or "00000000-0000-0000-0000-000000000001"
        input_dto = CreateApiKeyInput(**body)
        result = await self._use_case.execute(input_dto)
        return Response(
            status_code=201,
            body={
                "success": True,
                "message": "created",
                "data": ApiKeyResponse(
                    id=result.id,
                    name=result.name,
                    key_prefix=result.key_prefix,
                    status=result.status.value if hasattr(result.status, "value") else result.status,
                ).model_dump(),
            },
        )
