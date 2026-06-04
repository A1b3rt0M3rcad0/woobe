from fastapi import Request as FastAPIRequest
from fastapi.responses import StreamingResponse

from modules.runtime.service.ask_agent_stream_service import AskAgentStreamService
from modules.runtime.service.dtos import AskInput


async def handle_ask_stream(
    fastapi_request: FastAPIRequest,
    service: AskAgentStreamService,
) -> StreamingResponse:
    body: dict = await fastapi_request.json()
    input_dto = AskInput(**body)

    return StreamingResponse(
        service.generate(input_dto),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
