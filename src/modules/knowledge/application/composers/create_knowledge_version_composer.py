import warnings

warnings.warn(
    "modules.knowledge.application.composers.create_knowledge_version_composer is deprecated. "
    "Use modules.agent.application.composers.create_knowledge_version_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.create_knowledge_version_composer import create_knowledge_version_composer  # noqa: E402, F401
