import warnings

warnings.warn(
    "modules.knowledge.application.composers.upload_document_composer is deprecated. "
    "Use modules.agent.application.composers.upload_document_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.upload_document_composer import upload_document_composer  # noqa: E402, F401
