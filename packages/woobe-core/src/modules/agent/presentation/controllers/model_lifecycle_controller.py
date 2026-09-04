from uuid import UUID

from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


def _entity_payload(item):
    if isinstance(item, dict):
        return item
    payload = {
        "id": getattr(item, "id", None),
        "project_id": getattr(item, "project_id", None),
        "name": getattr(item, "name", None),
        "status": getattr(item, "status", None),
        "created_at": getattr(item, "created_at", None),
        "updated_at": getattr(item, "updated_at", None),
        "metadata": getattr(item, "metadata", None),
    }
    if hasattr(item, "provider"):
        payload["provider"] = getattr(item, "provider", None)
    if hasattr(item, "provider_credential_id"):
        payload["provider_credential_id"] = getattr(item, "provider_credential_id", None)
    if hasattr(item, "model"):
        payload["model"] = getattr(item, "model", None)
    if hasattr(item, "last_validated_at"):
        payload["last_validated_at"] = getattr(item, "last_validated_at", None)
    return payload


class ModelLifecycleController(Controller):
    def __init__(self, use_case, *, path_param: str, body: bool = False) -> None:
        self._use_case = use_case
        self._path_param = path_param
        self._body = body

    async def handle(self, request):
        item_id = UUID(request.path_params[self._path_param])
        if self._body:
            result = await self._use_case.execute(item_id, request.body or {})
        else:
            result = await self._use_case.execute(item_id)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": _entity_payload(result)},
        )

