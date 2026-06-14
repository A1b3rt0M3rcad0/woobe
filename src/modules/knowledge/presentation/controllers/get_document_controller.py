import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.get_document_controller is deprecated. "
    "Use modules.agent.presentation.controllers.get_document_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.get_document_controller import GetDocumentController  # noqa: E402, F401
