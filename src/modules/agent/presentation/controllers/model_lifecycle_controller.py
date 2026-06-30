from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


class ModelLifecycleController(Controller):
    def __init__(self, use_case) -> None:
        self._use_case = use_case

    async def handle(self, request):
        result = await self._use_case.execute(request.path_params.get("provider_model_id"))
        return Response(status_code=200, body={"success": True, "message": "ok", "data": result})
