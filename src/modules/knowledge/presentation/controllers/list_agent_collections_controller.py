from modules.knowledge.presentation.mappers import agent_collection_output_to_response
from modules.knowledge.service.use_cases import ListAgentCollectionsUseCase
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class ListAgentCollectionsController(Controller):
    def __init__(self, use_case: ListAgentCollectionsUseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = request.query_params.get("agent_id")
        if not agent_id:
            return Response(
                status_code=200,
                body={"success": True, "message": "ok", "data": []},
            )
        result = await self._use_case.execute(agent_id)
        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "ok",
                "data": [agent_collection_output_to_response(r).model_dump() for r in result],
            },
        )
