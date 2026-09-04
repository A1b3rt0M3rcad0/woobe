from modules.agent.application.interfaces.use_case import UseCase
from typing import Any, cast
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError

from modules.agent.application.dtos.knowledge_dtos import UpdateCollectionInput
from modules.agent.presentation.mappers import collection_to_response
from shared.contracts.errors import NotFoundError, ValidationError
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


class UpdateCollectionController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        try:
            body = request.body or {}
            payload: dict[str, Any] = {"collection_id": cast(UUID, request.params.get("collection_id"))}
            if "name" in body:
                payload["name"] = body.get("name")
            if "description" in body:
                payload["description"] = body.get("description")

            input_dto = UpdateCollectionInput(**payload)
            result = await self._use_case.execute(input_dto)
            return OperationResult(
                outcome=OperationOutcome.SUCCESS,
                body={
                    "success": True,
                    "message": "ok",
                    "data": collection_to_response(result).model_dump(),
                },
            )
        except NotFoundError as e:
            return OperationResult(
                outcome=OperationOutcome.NOT_FOUND,
                body={"success": False, "message": str(e), "data": None},
            )
        except (ValidationError, PydanticValidationError) as e:
            return OperationResult(
                outcome=OperationOutcome.UNPROCESSABLE,
                body={"success": False, "message": str(e), "data": None},
            )

