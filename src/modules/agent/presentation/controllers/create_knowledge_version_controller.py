from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import knowledge_version_to_response
from modules.agent.application.dtos import CreateKnowledgeVersionInput
from shared.contracts.errors import ValidationError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class CreateKnowledgeVersionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            body = {**request.body, **request.params}
            input_dto = CreateKnowledgeVersionInput(**body)
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=201,
                body={
                    "success": True,
                    "message": "created",
                    "data": knowledge_version_to_response(result).model_dump(),
                },
            )
        except ValidationError as e:
            return Response(
                status_code=422,
                body={"success": False, "message": str(e), "data": None},
            )
