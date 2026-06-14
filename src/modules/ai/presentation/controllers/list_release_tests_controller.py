import warnings

warnings.warn(
    "modules.ai.presentation.controllers.list_release_tests_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_release_tests_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_release_tests_controller import ListReleaseTestsController  # noqa: F401, E402
