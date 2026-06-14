import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.upload_document_controller is deprecated. "
    "Use modules.agent.presentation.controllers.upload_document_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.upload_document_controller import UploadDocumentController  # noqa: E402, F401
