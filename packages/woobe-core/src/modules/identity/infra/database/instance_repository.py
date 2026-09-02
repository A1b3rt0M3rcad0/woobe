from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from modules.identity.application.instance_types import InstanceState
from modules.identity.application.interfaces.instance import InstanceRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork


class SQLAlchemyInstanceRepository(InstanceRepository):
    def __init__(self, uow: IdentityUnitOfWork) -> None:
        self._uow = uow

    async def get_state(self) -> InstanceState:
        row = (
            await self._uow.session.execute(
                text(
                    """
                    SELECT owner_user_id, initialized_at, signup_mode, telemetry_enabled
                    FROM identity.instance_settings
                    WHERE id = 1
                    """
                )
            )
        ).mappings().one_or_none()
        user_count = int(
            (await self._uow.session.execute(text("SELECT count(*) FROM identity.users"))).scalar_one()
            or 0
        )
        return InstanceState(
            owner_user_id=(UUID(str(row["owner_user_id"])) if row is not None and row["owner_user_id"] is not None else None),
            initialized_at=(row["initialized_at"] if row is not None else None),
            signup_mode=(str(row["signup_mode"]) if row is not None else "bootstrap"),
            telemetry_enabled=(bool(row["telemetry_enabled"]) if row is not None else False),
            user_count=user_count,
        )

    async def has_active_invite(self, email: str) -> bool:
        pending_invite = (
            await self._uow.session.execute(
                text(
                    """
                    SELECT 1
                    FROM identity.workspace_invites
                    WHERE lower(email) = :email
                      AND status = 'pending'
                      AND expires_at > now()
                    LIMIT 1
                    """
                ),
                {"email": email.strip().lower()},
            )
        ).scalar_one_or_none()
        return pending_invite is not None

    async def claim_bootstrap(self, now: datetime) -> bool:
        result = await self._uow.session.execute(
            text(
                """
                INSERT INTO identity.instance_settings
                    (id, owner_user_id, initialized_at, signup_mode,
                     telemetry_enabled, created_at, updated_at)
                VALUES
                    (1, NULL, NULL, 'invite_only', false, :now, :now)
                ON CONFLICT (id) DO NOTHING
                RETURNING id
                """
            ),
            {"now": now},
        )
        return result.scalar_one_or_none() is not None

    async def set_owner(self, owner_user_id: UUID, now: datetime) -> None:
        await self._uow.session.execute(
            text(
                """
                UPDATE identity.instance_settings
                SET owner_user_id = :owner_user_id,
                    initialized_at = :now,
                    updated_at = :now
                WHERE id = 1
                """
            ),
            {"owner_user_id": owner_user_id, "now": now},
        )

    async def find_existing_owner(self, email: str) -> UUID | None:
        owner = (
            await self._uow.session.execute(
                text(
                    """
                    SELECT u.id
                    FROM identity.users AS u
                    JOIN identity.workspace_members AS member
                      ON member.user_id = u.id
                    WHERE lower(u.email) = :email
                      AND u.status = 'active'
                      AND member.status = 'active'
                      AND member.role = 'owner'
                    LIMIT 1
                    """
                ),
                {"email": email.strip().lower()},
            )
        ).scalar_one_or_none()
        return UUID(str(owner)) if owner is not None else None

    async def initialize_existing_owner(
        self,
        owner_user_id: UUID,
        now: datetime,
    ) -> bool:
        result = await self._uow.session.execute(
            text(
                """
                INSERT INTO identity.instance_settings
                    (id, owner_user_id, initialized_at, signup_mode,
                     telemetry_enabled, created_at, updated_at)
                VALUES
                    (1, :owner_user_id, :now, 'invite_only', false, :now, :now)
                ON CONFLICT (id) DO NOTHING
                RETURNING owner_user_id
                """
            ),
            {"owner_user_id": owner_user_id, "now": now},
        )
        return result.scalar_one_or_none() is not None
