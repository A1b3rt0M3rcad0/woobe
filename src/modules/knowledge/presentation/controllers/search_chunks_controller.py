import warnings

warnings.warn(
    "modules.knowledge.presentation.controllers.search_chunks_controller is deprecated. "
    "Use modules.agent.presentation.controllers.search_chunks_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.search_chunks_controller import SearchChunksController  # noqa: E402, F401
