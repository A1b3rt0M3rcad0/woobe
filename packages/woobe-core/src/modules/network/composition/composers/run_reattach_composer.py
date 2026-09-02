from __future__ import annotations

from collections.abc import Callable

from modules.network.composition.factories.network_uow_factory import build_network_read_uow
from modules.network.composition.resources import EXECUTION_STATE_STORE, SETTINGS
from modules.network.infra.database.runtime_transaction_runner import (
    NetworkRuntimeTransactionRunner,
)
from modules.network.infra.execution.network_run_reattach_service import (
    NetworkRunReattachService,
)
from modules.network.presentation.http.controllers.public_runtime_wait_controller import (
    PublicNetworkRunWaitController,
)
from modules.network.presentation.http.controllers.run_reattach_controller import (
    NetworkRunReattachController,
)


def _build_service() -> NetworkRunReattachService:
    transactions = NetworkRuntimeTransactionRunner(build_network_read_uow)
    return NetworkRunReattachService(
        transactions=transactions,
        state_store=EXECUTION_STATE_STORE,
        heartbeat_seconds=SETTINGS.network_stream_heartbeat_seconds,
    )


def active_network_run_composer() -> Callable:
    return NetworkRunReattachController(_build_service()).active


def attach_network_run_composer() -> Callable:
    return NetworkRunReattachController(_build_service()).attach


def wait_network_run_composer() -> Callable:
    controller = PublicNetworkRunWaitController(
        _build_service(),
        timeout_seconds=min(
            SETTINGS.runtime_total_timeout_seconds,
            SETTINGS.network_timeout_hard_seconds,
        ),
    )
    return controller.wait


__all__ = [
    "active_network_run_composer",
    "attach_network_run_composer",
    "wait_network_run_composer",
]
