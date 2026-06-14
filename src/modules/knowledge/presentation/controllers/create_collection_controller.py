import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.create_collection_controller is deprecated. "
    "Use modules.agent.presentation.controllers.create_collection_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.create_collection_controller import CreateCollectionController  # noqa: E402, F401
