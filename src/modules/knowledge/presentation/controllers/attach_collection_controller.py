import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.attach_collection_controller is deprecated. "
    "Use modules.agent.presentation.controllers.attach_collection_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.attach_collection_controller import AttachCollectionController  # noqa: E402, F401
