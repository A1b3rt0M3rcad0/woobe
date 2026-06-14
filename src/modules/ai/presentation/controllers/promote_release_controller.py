import warnings

warnings.warn(
    "modules.ai.presentation.controllers.promote_release_controller is deprecated. "
    "Use modules.agent.presentation.controllers.promote_release_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.promote_release_controller import PromoteReleaseController  # noqa: F401, E402
