import warnings

warnings.warn(
    "modules.ai.presentation.controllers.list_releases_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_releases_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_releases_controller import ListReleasesController  # noqa: F401, E402
