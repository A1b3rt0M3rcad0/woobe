import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.list_documents_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_documents_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_documents_controller import ListDocumentsController  # noqa: E402, F401
