from modules.agent.application.interfaces.use_case import UseCase
from typing import cast
from uuid import UUID

from shared.contracts.errors import NotFoundError
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class DetachCollectionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            link_id = cast(UUID, request.params.get("link_id"))
            await self._use_case.execute(link_id)
            return Response(
                status_code=200,
                body={"success": True, "message": "deleted", "data": None},
            )
        except NotFoundError as e:
            return Response(
                status_code=404,
                body={"success": False, "message": str(e), "data": None},
            )
