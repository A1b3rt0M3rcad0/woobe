import warnings

warnings.warn(
    "modules.knowledge.application.composers.list_collections_composer is deprecated. "
    "Use modules.agent.application.composers.list_collections_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_collections_composer import list_collections_composer  # noqa: E402, F401
