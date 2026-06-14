import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.list_collections_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_collections_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_collections_controller import ListCollectionsController  # noqa: E402, F401
