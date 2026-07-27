from typing import Any, Protocol
from uuid import UUID

from modules.agent.application.dtos import RollbackReleaseInput
from modules.agent.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class RollbackReleaseUseCaseProtocol(Protocol):
    async def execute(
        self,
        agent_id: UUID,
        release_id: UUID,
        input_dto: RollbackReleaseInput,
        **kwargs: Any,
    ) -> Any: ...


def _release_payload(release):
    data = release_to_response(release).model_dump()
    data["provider_model_id"] = getattr(release, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(release, "fallback_provider_model_id", None)
    return data


class RollbackReleaseController(Controller):
    def __init__(self, use_case: RollbackReleaseUseCaseProtocol) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        agent_id = UUID(request.path_params["agent_id"])
        release_id = UUID(request.path_params["release_id"])
        body = request.body or {}
        input_dto = RollbackReleaseInput(**body)
        object.__setattr__(input_dto, "change_description", body.get("change_description"))
        result = await self._use_case.execute(agent_id, release_id, input_dto)
        return Response(
            status_code=200,
            body={"success": True, "data": _release_payload(result)},
        )
