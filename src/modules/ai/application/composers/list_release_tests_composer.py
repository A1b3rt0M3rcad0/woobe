import warnings

warnings.warn(
    "modules.ai.application.composers.list_release_tests_composer is deprecated. "
    "Use modules.agent.application.composers.list_release_tests_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_release_tests_composer import list_release_tests_composer  # noqa: E402, F401

__all__ = ["list_release_tests_composer"]
