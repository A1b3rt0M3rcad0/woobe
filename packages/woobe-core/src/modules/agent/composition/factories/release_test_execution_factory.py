from modules.agent.application.use_cases.execute_release_test import ExecuteReleaseTest
from modules.agent.composition.factories.agent_uow_factory import build_agent_uow
from modules.agent.composition.factories.ask_agent_runtime_factory import (
    build_ask_agent_handler,
)
from modules.agent.composition.resources import SETTINGS
from modules.agent.infra.database.release_test_execution_store import (
    SQLReleaseTestExecutionStore,
)
from modules.agent.infra.execution.release_test_runtime import NativeReleaseTestRuntime
from modules.agent.presentation.controllers.execute_release_test_controller import (
    ExecuteReleaseTestController,
)


def build_release_test_execution_handler():
    # Commit a pending test before long-lived execution; finish in a separate
    # short Agent UOW. The native Run keeps its existing transaction ownership.
    store = SQLReleaseTestExecutionStore(build_agent_uow)
    runtime = NativeReleaseTestRuntime(build_ask_agent_handler(SETTINGS))
    return ExecuteReleaseTestController(ExecuteReleaseTest(store, runtime)).handle
