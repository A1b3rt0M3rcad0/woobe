from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from modules.package.domain.errors import PackageError


class OperationState(StrEnum):
    ACCEPTED = "accepted"
    RESOLVING = "resolving"
    MATERIALIZING = "materializing"
    VERIFYING = "verifying"
    WAITING_DEPENDENCY = "waiting_dependency"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


TERMINAL_STATES = frozenset(
    {OperationState.SUCCEEDED, OperationState.FAILED, OperationState.CANCELLED}
)
TRANSITIONS = {
    OperationState.ACCEPTED: {
        OperationState.RESOLVING,
        OperationState.CANCELLING,
        OperationState.FAILED,
    },
    OperationState.RESOLVING: {
        OperationState.MATERIALIZING,
        OperationState.WAITING_DEPENDENCY,
        OperationState.CANCELLING,
        OperationState.FAILED,
    },
    OperationState.MATERIALIZING: {
        OperationState.VERIFYING,
        OperationState.WAITING_DEPENDENCY,
        OperationState.CANCELLING,
        OperationState.FAILED,
    },
    OperationState.VERIFYING: {
        OperationState.SUCCEEDED,
        OperationState.WAITING_DEPENDENCY,
        OperationState.CANCELLING,
        OperationState.FAILED,
    },
    OperationState.WAITING_DEPENDENCY: {
        OperationState.RESOLVING,
        OperationState.CANCELLING,
        OperationState.FAILED,
    },
    OperationState.CANCELLING: {OperationState.CANCELLED, OperationState.FAILED},
}


def transition(current: str, target: str):
    current, target = OperationState(current), OperationState(target)
    if target != current and target not in TRANSITIONS.get(current, ()):
        raise PackageError(
            "PACKAGE_OPERATION_STATE", "Operation does not allow this state transition"
        )
    return target


@dataclass(frozen=True)
class Effect:
    key: str
    owner: str
    action: str
    component: str | None
    permission: str
    state: OperationState = OperationState.MATERIALIZING

    def public(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "owner": self.owner,
            "action": self.action,
            "component": self.component,
            "permission": self.permission,
            "state": self.state.value,
        }


def operation_status(record) -> dict[str, Any]:
    """Only explicit operational evidence is exposed; protected payloads stay private."""
    state = OperationState(record.state)
    return {
        "operation_id": str(record.id),
        "project_id": str(record.project_id),
        "package_schema_version": "1.0",
        "artifact_digest": record.artifact_digest,
        "state": state.value,
        "terminal": state in TERMINAL_STATES,
        "phase": record.phase,
        "phases_completed": record.phases_completed,
        "phases_total": record.phases_total,
        "revision": record.revision,
        "next_poll_after_ms": 2000 if state not in TERMINAL_STATES else None,
        "lifecycle_state": record.lifecycle_state,
        "configuration_ready": record.configuration_ready,
        "execution_ready": record.execution_ready,
        "inventory": record.inventory,
        "dependencies": record.dependencies,
        "diagnostics": record.diagnostics,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
