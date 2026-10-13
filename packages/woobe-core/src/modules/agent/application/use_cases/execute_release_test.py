from time import monotonic
import json

from modules.agent.application.use_cases.structured_output_contract import validate_output_against_contract

from modules.agent.application.interfaces.release_test_execution import (
    ReleaseTestExecutionStore,
    ReleaseTestRuntime,
)


class ExecuteReleaseTest:
    def __init__(self, store: ReleaseTestExecutionStore, runtime: ReleaseTestRuntime):
        self._store, self._runtime = store, runtime

    async def execute(self, request, principal):
        test = await self._store.prepare(request, principal)
        if getattr(test, "replayed", False):
            return test
        started = monotonic()
        actual, errors = None, []
        if getattr(test, "contract_missing", False):
            return await self._store.finish(test.id,
                actual_output={"provider_completed": False, "output_valid": False, "contract_missing": True},
                errors=[{"code": "CONTRACT_MISSING"}], latency_ms=0)
        try:
            frozen = getattr(test, "execution_snapshot", None)
            result = await self._runtime.run(request, principal, test.id, snapshot=frozen) if frozen else await self._runtime.run(request, principal, test.id)
            actual = {
                "answer": result.get("answer"),
                "parsed_output": result.get("parsed_output"),
                "run_id": str(result["run_id"]) if result.get("run_id") else None,
            }
            schema = getattr(test, "validation_schema", None)
            if schema is not None:
                parsed = result.get("parsed_output")
                if parsed is None:
                    try:
                        parsed = json.loads(result.get("answer") or "")
                    except (ValueError, TypeError):
                        pass
                actual["parsed_output"] = parsed
                invalid = parsed is None or bool(validate_output_against_contract(parsed, schema))
                actual.update(provider_completed=True, output_valid=not invalid, contract_missing=False)
                if invalid:
                    errors.append({"code": "OUTPUT_VALIDATION_FAILED"})
            if result.get("output_parse_error") and not errors:
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
