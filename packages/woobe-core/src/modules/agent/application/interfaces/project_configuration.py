"""Host-supplied configuration port; Agent never imports Core persistence."""
from collections.abc import Callable
from typing import Any, Protocol


class ProjectConfigurationPort(Protocol):
    async def register_references(self, dependencies, *, retained=True): ...
    async def acquire(self, *, project_id, run_id, environment, dependencies): ...
    async def require_bridge(self, *, required_processes): ...
    async def adopt(self, **source): ...
    async def rotate_legacy(self, **source): ...
    async def record_validation(self, **evidence): ...
    async def resolve(self, *, project_id, run_id, consumer_kind, consumer_id, field_path, destination): ...


_factory: Callable[[Any], ProjectConfigurationPort] | None = None


def configure_project_configuration(factory: Callable[[Any], ProjectConfigurationPort] | None) -> None:
    """Composition hosts install this adapter before accepting work."""
    global _factory
    _factory = factory


def configuration_for_session(session) -> ProjectConfigurationPort | None:
    return _factory(session) if _factory is not None else None


_runtime_resolver = None


def configure_runtime_configuration_resolver(resolver):
    global _runtime_resolver
    _runtime_resolver = resolver


async def resolve_runtime_configuration(**identity):
    from shared.contracts.project_configuration import ConfigurationError
    if _runtime_resolver is None:
        raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
    return await _runtime_resolver(**identity)


from contextvars import ContextVar
current_tool_configuration = ContextVar("tool_configuration", default=None)
