from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.use_cases.execute_release_test import ExecuteReleaseTest


@pytest.mark.asyncio
@pytest.mark.parametrize("run_id", ["native-run", uuid4()])
@pytest.mark.parametrize(
    "expected,errors",
    [
        (None, []),
        ({"answer": "Actual"}, []),
        ({"answer": "Different"}, [{"code": "EXPECTED_OUTPUT_MISMATCH"}]),
    ],
)
async def test_release_test_executes_and_persists_terminal_assertion_result(
    expected, errors, run_id
):
    test_id = uuid4()
    store = SimpleNamespace(
        prepare=AsyncMock(return_value=SimpleNamespace(id=test_id)),
        finish=AsyncMock(return_value="saved-result"),
    )
    runtime = SimpleNamespace(
        run=AsyncMock(return_value={"answer": "Actual", "run_id": run_id})
    )
    request = SimpleNamespace(expected_output=expected)
    assert (
        await ExecuteReleaseTest(store, runtime).execute(request, "principal")
        == "saved-result"
    )
    runtime.run.assert_awaited_once_with(request, "principal", test_id)
    finished = store.finish.await_args.kwargs
    assert finished["actual_output"] == {
        "answer": "Actual",
        "parsed_output": None,
        "run_id": str(run_id),
    }
    assert finished["errors"] == errors and finished["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_execution_error_is_persisted_without_provider_credentials():
    store = SimpleNamespace(
        prepare=AsyncMock(return_value=SimpleNamespace(id=uuid4())), finish=AsyncMock()
    )
    runtime = SimpleNamespace(
        run=AsyncMock(side_effect=RuntimeError("secret=private-provider-key"))
    )
    await ExecuteReleaseTest(store, runtime).execute(
        SimpleNamespace(expected_output=None), "principal"
    )
    assert store.finish.await_args.kwargs["errors"] == [
        {"code": "RUNTIME_EXECUTION_FAILED"}
    ]
    assert "private-provider-key" not in str(store.finish.await_args)


@pytest.mark.asyncio
async def test_denied_prepare_never_executes_the_agent():
    store = SimpleNamespace(
        prepare=AsyncMock(side_effect=PermissionError("denied")), finish=AsyncMock()
    )
    runtime = SimpleNamespace(run=AsyncMock())
    with pytest.raises(PermissionError):
        await ExecuteReleaseTest(store, runtime).execute(SimpleNamespace(), "principal")
    runtime.run.assert_not_awaited()
    store.finish.assert_not_awaited()
