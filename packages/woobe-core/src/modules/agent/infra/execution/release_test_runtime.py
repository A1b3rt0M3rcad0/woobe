from shared.presentation.contracts import OperationRequest
from shared.contracts.errors import ValidationError


class NativeReleaseTestRuntime:
    def __init__(self, handler):
        self._handler = handler

    async def run(self, request, principal, test_id):
        response = await self._handler(
            OperationRequest(
                principal=principal,
                body={
                    "project_id": request.project_id,
                    "agent_id": request.agent_id,
                    "message": request.message,
                    "loaded_release_id": request.release_id,
                    "execution_context": request.environment,
                    "external_context": request.external_context,
                    "metadata": {"release_test_id": str(test_id)},
                },
            )
        )
        if (
            response.outcome.value != "success"
            or response.body.get("success") is not True
        ):
            raise ValidationError("Native test execution failed")
        return response.body["data"]
