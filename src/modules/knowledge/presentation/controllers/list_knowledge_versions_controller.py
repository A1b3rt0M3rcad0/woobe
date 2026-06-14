import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.list_knowledge_versions_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_knowledge_versions_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_knowledge_versions_controller import ListKnowledgeVersionsController  # noqa: E402, F401
