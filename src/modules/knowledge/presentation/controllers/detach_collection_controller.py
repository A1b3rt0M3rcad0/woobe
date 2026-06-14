import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.detach_collection_controller is deprecated. "
    "Use modules.agent.presentation.controllers.detach_collection_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.detach_collection_controller import DetachCollectionController  # noqa: E402, F401
