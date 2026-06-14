import warnings

warnings.warn(
    "modules.ai.presentation.controllers.create_release_controller is deprecated. "
    "Use modules.agent.presentation.controllers.create_release_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.create_release_controller import CreateReleaseController  # noqa: F401, E402
