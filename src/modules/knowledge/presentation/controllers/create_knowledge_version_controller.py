import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.create_knowledge_version_controller is deprecated. "
    "Use modules.agent.presentation.controllers.create_knowledge_version_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.create_knowledge_version_controller import CreateKnowledgeVersionController  # noqa: E402, F401
