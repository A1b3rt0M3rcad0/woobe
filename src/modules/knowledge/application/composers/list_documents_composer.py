import warnings

warnings.warn(
    "modules.knowledge.application.composers.list_documents_composer is deprecated. "
    "Use modules.agent.application.composers.list_documents_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_documents_composer import list_documents_composer  # noqa: E402, F401
