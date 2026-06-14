import warnings

warnings.warn(
    "modules.ai.presentation.routes is deprecated. "
    "Use modules.agent.presentation.routes instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.routes import router  # noqa: F401, E402
