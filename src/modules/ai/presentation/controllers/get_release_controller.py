import warnings

warnings.warn(
    "modules.ai.presentation.controllers.get_release_controller is deprecated. "
    "Use modules.agent.presentation.controllers.get_release_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.get_release_controller import GetReleaseController  # noqa: F401, E402
