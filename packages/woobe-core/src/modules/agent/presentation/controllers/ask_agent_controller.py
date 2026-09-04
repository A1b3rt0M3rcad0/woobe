from modules.agent.application.interfaces.use_case import UseCase
import logging

from modules.agent.presentation.schemas import AskResponse, UsageResponse
from modules.agent.application.dtos import AskInput
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller

logger = logging.getLogger(__name__)


class AskAgentController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            input_dto = AskInput(**request.body)
            result = await self._use_case.execute(input_dto)

            data = AskResponse(
                run_id=result.run_id,
                answer=result.answer,
                session_id=result.session_id,
                message_id=result.message_id,
                usage=UsageResponse(
                    input_tokens=result.usage.input_tokens if result.usage else None,
                    output_tokens=result.usage.output_tokens if result.usage else None,
                    total_tokens=result.usage.total_tokens if result.usage else None,
                    cost_usd=result.usage.cost_usd if result.usage else None,
                ),
                sources=result.sources or [],
                tool_calls=result.tool_calls or [],
                trace_id=result.trace_id,
                model=result.model,
                provider=result.provider,
                fallback_used=result.fallback_used or False,
                latency_ms=result.latency_ms,
                parsed_output=result.parsed_output,
                output_parse_error=result.output_parse_error,
            ).model_dump()
            data["provider_model_id"] = result.provider_model_id
            data["provider_credential_id"] = result.provider_credential_id
            data["fallback_provider_model_id"] = result.fallback_provider_model_id
            data["fallback_credential_id"] = result.fallback_credential_id
            data["fallback_info"] = result.fallback_info
            data["execution_events"] = result.execution_events
            data["diagnostics"] = result.diagnostics

            return OperationResult(
                outcome=OperationOutcome.SUCCESS,
                body={
                    "success": True,
                    "message": "Agent answered successfully",
                    "data": data,
                },
            )

        except NotFoundError as e:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": str(e), "data": None},
            )
        except ConflictError as e:
            return OperationResult(
                outcome=OperationOutcome.CONFLICT,
                body={"success": False, "message": str(e), "data": None},
            )
        except ValidationError as e:
            return OperationResult(
                outcome=OperationOutcome.INVALID,
                body={"success": False, "message": str(e), "data": None},
            )
        except NotImplementedError as e:
            return OperationResult(
                outcome=OperationOutcome.NOT_IMPLEMENTED,
                body={"success": False, "message": str(e), "data": None},
            )
        except ValueError as e:
            return OperationResult(
                outcome=OperationOutcome.INVALID,
                body={"success": False, "message": str(e), "data": None},
            )
        except Exception as e:
            logger.exception("Unexpected error in ask agent: %s", e)
            return OperationResult(
                outcome=OperationOutcome.FAILURE,
                body={"success": False, "message": "Internal server error", "data": None},
            )

