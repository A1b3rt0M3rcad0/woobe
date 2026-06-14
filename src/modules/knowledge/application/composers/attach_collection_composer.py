import warnings

warnings.warn(
    "modules.knowledge.application.composers.attach_collection_composer is deprecated. "
    "Use modules.agent.application.composers.attach_collection_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.attach_collection_composer import attach_collection_composer  # noqa: E402, F401
