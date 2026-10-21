from collections.abc import Callable

from modules.agent.composition.factories.provider_discovery_factory import build_provider_discovery_handler


def list_available_provider_models_composer() -> Callable:
    """Discovery releases its authorization transaction before provider I/O."""
    return build_provider_discovery_handler()
