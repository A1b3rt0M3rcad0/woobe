from datetime import UTC, datetime
from uuid import UUID
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.core.infra.database.control_key_models import (
    ControlKeyProjectGrantModel,
    WorkspaceControlKeyModel,
)
from modules.core.infra.database.models import ProjectModel
from shared.contracts.errors import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
)
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.security.control_plane import (
    conditions_are_subset,
    require_expiration_ceiling,
)


class SqlApiKeyDelegationPolicy:
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._session_or_uow = session

    async def validate(
        self,
        *,
        actor_key_id: UUID,
        project_id: UUID,
        scopes: list[str],
        conditions: dict[str, Any],
        expires_at: datetime | None,
    ) -> datetime | None:
        session = (
            self._session_or_uow.session
            if isinstance(self._session_or_uow, UnitOfWork)
            else self._session_or_uow
        )
        actor = (
            await session.execute(
                select(WorkspaceControlKeyModel)
                .where(WorkspaceControlKeyModel.id == actor_key_id)
                .with_for_update(read=True)
            )
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if (
            actor is None
            or actor.status != "active"
            or actor.revoked_at is not None
            or (actor.expires_at is not None and actor.expires_at <= now)
        ):
            raise AuthenticationError("Control credential is inactive")
        project_workspace = (
            await session.execute(
                select(ProjectModel.workspace_id).where(ProjectModel.id == project_id)
            )
        ).scalar_one_or_none()
        if project_workspace != actor.workspace_id:
            raise NotFoundError("Resource not found")
        grant = (
            await session.execute(
                select(ControlKeyProjectGrantModel)
                .where(
                    ControlKeyProjectGrantModel.control_key_id == actor_key_id,
                    ControlKeyProjectGrantModel.project_id == project_id,
                )
                .with_for_update(read=True)
            )
        ).scalar_one_or_none()
        if grant is None:
            raise NotFoundError("Resource not found")
        scope_permissions = {
            "runtime:execute": "run:execute",
            "traces:read": "observability:read",
            "usage:read": "usage:read",
        }
        required = {"api_key:write"} | {
            scope_permissions.get(scope, "unsupported:scope") for scope in scopes
        }
        if not required <= set(grant.permissions):
            raise AuthorizationError("Runtime scopes exceed control authority")
        if not conditions_are_subset(conditions, grant.conditions):
            raise AuthorizationError("Runtime binding exceeds grant conditions")
        ceilings = [
            value
            for value in (actor.expires_at, actor.delegation_expires_at)
            if value is not None
        ]
        try:
            require_expiration_ceiling(expires_at, min(ceilings) if ceilings else None)
        except ValueError as exc:
            raise AuthorizationError(str(exc)) from exc

        return min(ceilings) if ceilings else None
