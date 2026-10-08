from time import monotonic

from modules.agent.application.interfaces.release_test_execution import (
    ReleaseTestExecutionStore,
    ReleaseTestRuntime,
)


class ExecuteReleaseTest:
    def __init__(self, store: ReleaseTestExecutionStore, runtime: ReleaseTestRuntime):
        self._store, self._runtime = store, runtime

    async def execute(self, request, principal):
        test = await self._store.prepare(request, principal)
        started = monotonic()
        actual, errors = None, []
        try:
            result = await self._runtime.run(request, principal, test.id)
            actual = {
                "answer": result.get("answer"),
                "parsed_output": result.get("parsed_output"),
                "run_id": str(result["run_id"]) if result.get("run_id") else None,
            }
            if result.get("output_parse_error"):
                errors.append({"code": "OUTPUT_VALIDATION_FAILED"})
            if request.expected_output is not None:
                candidate = result.get("parsed_output")
                if candidate is None:
                    candidate = {"answer": result.get("answer")}
                if candidate != request.expected_output:
                    errors.append({"code": "EXPECTED_OUTPUT_MISMATCH"})
        except Exception:
            # Provider/Tool exception text can contain credential material.
            errors.append({"code": "RUNTIME_EXECUTION_FAILED"})
        return await self._store.finish(
            test.id,
            actual_output=actual,
            errors=errors,
            latency_ms=int((monotonic() - started) * 1000),
        )
