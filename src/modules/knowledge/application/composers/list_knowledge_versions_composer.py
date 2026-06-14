import warnings

warnings.warn(
    "modules.knowledge.application.composers.list_knowledge_versions_composer is deprecated. "
    "Use modules.agent.application.composers.list_knowledge_versions_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_knowledge_versions_composer import list_knowledge_versions_composer  # noqa: E402, F401
