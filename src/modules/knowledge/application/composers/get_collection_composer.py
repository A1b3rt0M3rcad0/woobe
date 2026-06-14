import warnings

warnings.warn(
    "modules.knowledge.application.composers.get_collection_composer is deprecated. "
    "Use modules.agent.application.composers.get_collection_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.get_collection_composer import get_collection_composer  # noqa: E402, F401
