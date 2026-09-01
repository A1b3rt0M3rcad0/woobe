from modules.agent.application.interfaces.use_case import UseCase
from typing import cast
from uuid import UUID

from modules.agent.application.dtos import GetCollectionInput
from modules.agent.presentation.mappers import collection_to_response
from shared.contracts.errors import NotFoundError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class GetCollectionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_dto = GetCollectionInput(
                collection_id=cast(UUID, request.params.get("collection_id"))
            )
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
