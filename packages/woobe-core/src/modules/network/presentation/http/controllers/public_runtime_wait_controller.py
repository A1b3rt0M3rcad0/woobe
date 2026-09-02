from uuid import UUID

from fastapi import Request as FastAPIRequest
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from modules.network.application.interfaces.run_reattach import (
    NetworkRunReattachOperations,
)
from modules.network.presentation.mappers import (
    public_network_failure_message,
    public_network_run_payload,
)


class PublicNetworkRunWaitController:
    def __init__(
        self,
        operations: NetworkRunReattachOperations,
        *,
        timeout_seconds: float,
    ) -> None:
        self._operations = operations
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def _principal(request: FastAPIRequest) -> object | None:
        return getattr(request.state, "principal", None)

    async def wait(
        self,
        run_id: UUID,
        request: FastAPIRequest,
    ):
        run = await self._operations.wait_terminal(
            run_id=run_id,
            principal=self._principal(request),
            timeout_seconds=self._timeout_seconds,
        )
        payload = public_network_run_payload(run)
        if run.status == "completed":
            return {
                "success": True,
                "message": "ok",
                "data": payload,
            }

        status_code = 409 if run.status == "cancelled" else 503
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(
                {
                    "success": False,
                    "message": public_network_failure_message(run.failure_code)
                    or run.status,
                    "data": payload,
                }
            ),
        )
