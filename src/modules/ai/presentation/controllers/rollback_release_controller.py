import warnings

warnings.warn(
    "modules.ai.presentation.controllers.rollback_release_controller is deprecated. "
    "Use modules.agent.presentation.controllers.rollback_release_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.rollback_release_controller import RollbackReleaseController  # noqa: F401, E402
