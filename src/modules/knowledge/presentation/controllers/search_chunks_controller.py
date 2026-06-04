from modules.knowledge.presentation.mappers import chunk_output_to_response
from modules.knowledge.service.dtos import SearchChunksInput
from modules.knowledge.service.use_cases import SearchChunksUseCase
from shared.domain.errors import ValidationError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class SearchChunksController(Controller):
    def __init__(self, use_case: SearchChunksUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            body = request.body or {}
            input_dto = SearchChunksInput(
                collection_id=body["collection_id"],
                embedding=body.get("embedding", []),
                limit=body.get("limit", 10),
                threshold=body.get("threshold", 0.7),
            )
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=200,
                body={
                    "success": True,
                    "message": "ok",
                    "data": [chunk_output_to_response(r).model_dump() for r in result.results],
                },
            )
        except ValidationError as e:
            return Response(
                status_code=422,
                body={"success": False, "message": str(e), "data": None},
            )
