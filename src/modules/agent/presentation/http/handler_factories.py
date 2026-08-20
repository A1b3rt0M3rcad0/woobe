from __future__ import annotations

from collections.abc import Callable
from typing import Any


HandlerFactory = Callable[[], Any]
_HANDLER_FACTORIES: dict[str, HandlerFactory] = {}


def configure_handler_factories(factories: dict[str, HandlerFactory]) -> None:
    """Install the Agent HTTP handler factories during composition bootstrap."""
    _HANDLER_FACTORIES.clear()
    _HANDLER_FACTORIES.update(factories)


def resolve_handler_factory(name: str) -> HandlerFactory:
    try:
        return _HANDLER_FACTORIES[name]
    except KeyError as exc:
        raise RuntimeError(
            f"Agent HTTP handler factory {name!r} is not configured"
        ) from exc


def __getattr__(name: str):
    """Expose injected composer-compatible callables without importing composition."""
    if not name.endswith("_composer"):
        raise AttributeError(name)

    def factory():
        return resolve_handler_factory(name)()

    factory.__name__ = name
    return factory
