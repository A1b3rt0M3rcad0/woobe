from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos import SendMessageInput
from shared.presentation.interface.controller import Controller
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.contracts.errors import NotFoundError, ValidationError


class SendMessageController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            input_dto = SendMessageInput(**request.body)
            result = await self._use_case.execute(input_dto)
            return OperationResult(
                outcome=OperationOutcome.SUCCESS,
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
            return OperationResult(outcome=OperationOutcome.NOT_FOUND, body={"success": False, "message": str(e), "data": None})
        except ValidationError as e:
            return OperationResult(outcome=OperationOutcome.UNPROCESSABLE, body={"success": False, "message": str(e), "data": None})

