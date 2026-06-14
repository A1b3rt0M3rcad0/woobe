import warnings

warnings.warn(
    "modules.knowledge.presentation.routes is deprecated. Use modules.agent.presentation.routes instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.routes import knowledge_router as router  # noqa: E402, F401
