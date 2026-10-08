from modules.agent.application.interfaces.development_resources import (
    DevelopmentResources,
)
from shared.presentation.contracts import OperationResult


class DevelopmentResourceController:
    def __init__(self, resources: DevelopmentResources, action: str, fallback=None):
        self._resources, self._action, self._fallback = resources, action, fallback

    async def handle(self, request):
        if self._action == "prepare_existing":
            data = await self._resources.prepare_existing(
                request.body, request.path_params["agent_id"]
            )
        elif self._action == "reuse":
            data = await self._resources.reuse(request.body, request.principal)
        elif self._action == "reuse_frozen":
            data = await self._resources.reuse_frozen(request.body, request.principal)
        elif self._action == "DocumentLookup":
            data = await self._resources.find_artifact("Document", request.body)
        else:
            data = await self._resources.find_artifact(self._action, request.body)
            if data is None:
                return await self._fallback.handle(request)
        return OperationResult(body={"success": True, "data": data})
