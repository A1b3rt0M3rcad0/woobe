from modules.agent.application.interfaces.use_case import UseCase
from uuid import UUID

from modules.agent.presentation.mappers import release_to_response
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult


def _release_payload(release):
    data = release_to_response(release).model_dump()
    data["snapshot_kind"] = getattr(release, "snapshot_kind", None)
    data["provider_model_id"] = getattr(release, "provider_model_id", None)
    data["fallback_provider_model_id"] = getattr(release, "fallback_provider_model_id", None)
    return data


class GetReleaseController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        release_id = request.path_params["release_id"]
        result = await self._use_case.execute(UUID(release_id))
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "data": _release_payload(result)},
        )

