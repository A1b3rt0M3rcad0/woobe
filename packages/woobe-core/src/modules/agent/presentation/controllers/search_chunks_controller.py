from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.presentation.mappers import chunk_output_to_response
from modules.agent.application.dtos import SearchChunksInput
from shared.contracts.errors import ValidationError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class SearchChunksController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_dto = SearchChunksInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=200,
                body={
                    "success": True,
                    "message": "ok",
                    "data": [chunk_output_to_response(c).model_dump() for c in result.results],
                },
            )
        except ValidationError as e:
            return Response(
                status_code=422,
                body={"success": False, "message": str(e), "data": None},
            )
