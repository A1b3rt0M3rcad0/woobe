from __future__ import annotations

from typing import Any
from uuid import UUID

from shared.contracts.errors import ValidationError
from shared.runtime_environment import RUNTIME_ENVIRONMENTS, set_runtime_environment_enabled


class LegacyRuntimeStatusUpdateAdapter:
    """Keeps PATCH agent.status compatible without restoring global coupling."""

    def __init__(self, delegate: Any, uow: Any) -> None:
        self._delegate = delegate
        self._uow = uow

    async def execute(self, agent_id: UUID, input_dto: Any) -> Any:
        changes = input_dto.model_dump(exclude_unset=True)
        requested_status = changes.pop("status", None)
        status = getattr(requested_status, "value", requested_status)
        if status == "archived":
            # Archival is the explicit native lifecycle boundary, not a legacy
            # enable/disable shortcut. Run owner dependency and revision guards.
            changes["status"] = requested_status
        sanitized_input = type(input_dto)(**changes)
        result = await self._delegate.execute(agent_id, sanitized_input)

        if requested_status is None:
            return result

        status = getattr(requested_status, "value", requested_status)
        if status not in {"active", "inactive", "archived"}:
            raise ValidationError("Agent status must be active, inactive or archived")
        enabled = status == "active"
        for environment in RUNTIME_ENVIRONMENTS:
            await set_runtime_environment_enabled(
                self._uow.session,
                target_type="agent",
                target_id=agent_id,
                project_id=result.project_id,
                environment=environment,
                enabled=enabled,
                updated_by=None,
            )
        return result
