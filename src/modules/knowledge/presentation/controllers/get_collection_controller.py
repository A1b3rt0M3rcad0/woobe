from modules.knowledge.presentation.mappers import collection_to_response
from modules.knowledge.service.dtos import GetCollectionInput
from modules.knowledge.service.use_cases import GetCollectionUseCase
from shared.domain.errors import NotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class GetCollectionController(Controller):
    def __init__(self, use_case: GetCollectionUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            collection_id = request.path_params["collection_id"]
            input_dto = GetCollectionInput(collection_id=collection_id)
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=200,
                body={
                    "success": True,
                    "message": "ok",
                    "data": collection_to_response(result).model_dump(),
                },
            )
        except NotFoundError as e:
            return Response(
                status_code=404,
                body={"success": False, "message": str(e), "data": None},
            )
