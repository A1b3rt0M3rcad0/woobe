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
from modules.network.presentation.http.controllers.run_reattach_controller import (
    NetworkRunReattachController,
)


def _build_controller() -> NetworkRunReattachController:
    transactions = NetworkRuntimeTransactionRunner(build_network_read_uow)
    service = NetworkRunReattachService(
        transactions=transactions,
        state_store=EXECUTION_STATE_STORE,
        heartbeat_seconds=SETTINGS.network_stream_heartbeat_seconds,
    )
    return NetworkRunReattachController(service)


def active_network_run_composer() -> Callable:
    return _build_controller().active


def attach_network_run_composer() -> Callable:
    return _build_controller().attach


__all__ = ["active_network_run_composer", "attach_network_run_composer"]
