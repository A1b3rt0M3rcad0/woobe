"""Network service factories for synchronous process hosts."""

from modules.network.composition.resources import (
    EXECUTION_STATE_STORE,
    SESSION_FACTORY,
    SETTINGS,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.infra.services.boundary_service import NetworkBoundaryService
from modules.network.infra.services.rerun_service import NetworkRerunService
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION, LEGACY_STORAGE_VERSION


def _run_storage_version() -> str:
    return (
        EVENT_JOURNAL_STORAGE_VERSION
        if SETTINGS.run_persistence_mode == "event_journal"
        else LEGACY_STORAGE_VERSION
    )


def build_network_service() -> NetworkBoundaryService:
    from modules.network.composition.bootstrap import (
        install_network_service_extensions,
    )

    install_network_service_extensions()
    return NetworkBoundaryService(
        SESSION_FACTORY,
        hard_max_depth=SETTINGS.network_max_depth_hard,
        hard_max_invocations=SETTINGS.network_max_invocations_hard,
        hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
        runtime_control=RedisNetworkExecutionStore(EXECUTION_STATE_STORE),
        run_storage_version=_run_storage_version(),
    )


def build_network_rerun_service() -> NetworkRerunService:
    return NetworkRerunService(
        SESSION_FACTORY,
        run_storage_version=_run_storage_version(),
    )


__all__ = ["build_network_rerun_service", "build_network_service"]
