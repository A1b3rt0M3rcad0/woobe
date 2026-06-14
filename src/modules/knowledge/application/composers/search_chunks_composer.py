import warnings

warnings.warn(
    "modules.knowledge.application.composers.search_chunks_composer is deprecated. "
    "Use modules.agent.application.composers.search_chunks_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.search_chunks_composer import search_chunks_composer  # noqa: E402, F401
