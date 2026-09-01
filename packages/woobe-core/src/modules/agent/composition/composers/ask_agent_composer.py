from collections.abc import Callable

from modules.agent.composition.factories.ask_agent_runtime_factory import build_ask_agent_handler
from modules.agent.composition.resources import SETTINGS


def ask_agent_composer() -> Callable:
    """Compose the long-lived Agent Run without a global transaction wrapper."""

    return build_ask_agent_handler(SETTINGS)


__all__ = ["ask_agent_composer"]
