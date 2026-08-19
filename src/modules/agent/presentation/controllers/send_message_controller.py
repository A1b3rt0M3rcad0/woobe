from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import SendMessageInput
from shared.presentation.interface.controller import Controller
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.contracts.errors import NotFoundError, ValidationError


class SendMessageController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        try:
            input_dto = SendMessageInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return Response(
                status_code=200,
                body={
                    "success": True,
                    "message": "ok",
                    "data": {
                        "answer": result.message.content,
                        "session_id": str(result.session_id),
                        "message_id": str(result.message.id),
                        "usage": {
                            "input_tokens": result.message.input_tokens,
                            "output_tokens": result.message.output_tokens,
                            "cost_usd": result.message.cost_usd,
                        },
                    },
                },
            )
        except NotFoundError as e:
            return Response(status_code=404, body={"success": False, "message": str(e), "data": None})
        except ValidationError as e:
            return Response(status_code=422, body={"success": False, "message": str(e), "data": None})
