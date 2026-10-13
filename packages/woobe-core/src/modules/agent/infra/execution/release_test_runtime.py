from shared.presentation.contracts import OperationRequest
from shared.contracts.errors import ValidationError
from modules.agent.application.interfaces.release_test_execution import release_test_output_capture


class NativeReleaseTestRuntime:
    def __init__(self, handler):
        self._handler = handler

    async def run(self, request, principal, test_id, *, snapshot=None):
        capture = {}
        token = release_test_output_capture.set(capture)
        try:
            response = await self._handler(OperationRequest(
                principal=principal,
                body={
                    "project_id": request.project_id,
                    "agent_id": request.agent_id,
                    "message": request.message,
                    "loaded_release_id": None if snapshot and request.environment == "draft" else request.release_id,
                    "snapshot_override": snapshot if request.environment == "draft" else None,
                    "execution_context": request.environment,
                    "external_context": request.external_context,
                    "metadata": {"release_test_id": str(test_id)},
                },
            ))
        finally:
            release_test_output_capture.reset(token)
        if response.outcome.value != "success" or response.body.get("success") is not True:
            if capture:
                # The strict runtime still rejects the Run. Only its authorized
                # test wrapper receives private output evidence to record failure.
                return capture
            raise ValidationError("Native test execution failed")
        return response.body["data"]
