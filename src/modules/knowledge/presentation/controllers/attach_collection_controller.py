from modules.knowledge.presentation.mappers import attach_collection_output_to_response
from modules.knowledge.service.dtos import AttachCollectionInput
from modules.knowledge.service.use_cases import AttachCollectionUseCase
from shared.domain.errors import ConflictError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class AttachCollectionController(Controller):
    def __init__(self, use_case: AttachCollectionUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_dto = AttachCollectionInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=201,
                body={
                    "success": True,
                    "message": "created",
                    "data": attach_collection_output_to_response(result).model_dump(),
                },
            )
        except ConflictError as e:
            return Response(
                status_code=409,
                body={"success": False, "message": str(e), "data": None},
            )
