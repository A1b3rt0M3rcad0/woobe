import warnings

warnings.warn(
    "modules.ai.application.composers.create_release_test_composer is deprecated. "
    "Use modules.agent.application.composers.create_release_test_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.create_release_test_composer import create_release_test_composer  # noqa: E402, F401

__all__ = ["create_release_test_composer"]
