from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.contracts.errors import AuthenticationError, ConflictError, ValidationError
from shared.infra.crypto import decrypt_secret, encrypt_secret
from shared.infra.database.admin_idempotency import AdministrativeOperationModel
from shared.security.principal import (
    AuthenticatedPrincipal,
    ControlPlanePrincipal,
    SecurityPrincipal,
)


def principal_identity(actor: SecurityPrincipal) -> str:
    if isinstance(actor, AuthenticatedPrincipal):
        return f"user:{actor.user_id}"
    if isinstance(actor, ControlPlanePrincipal):
        return f"control:{actor.credential_id}"
    raise AuthenticationError("Administrative authentication required")


def canonical_digest(value: Any) -> bytes:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
            ensure_ascii=False,
        ).encode()
    ).digest()


class AdministrativeIdempotency:
    """Reserve and record in the same transaction as the accepted mutation."""

    def __init__(self, session: AsyncSession, *, encryption_key: str) -> None:
        self.session = session
        self.encryption_key = encryption_key
        self.record: AdministrativeOperationModel | None = None

    async def begin(
        self,
        *,
        key: str | None,
        actor: SecurityPrincipal,
        workspace_id: UUID,
        operation: str,
        payload: Any,
    ) -> dict[str, Any] | None:
        if key is None:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", key):
            raise ValidationError(
                "Idempotency key must be a bounded printable identifier"
            )
        identity = principal_identity(actor)
        digest = hashlib.sha256(key.encode()).digest()
        payload_digest = canonical_digest(payload)
        lock_material = [str(workspace_id), identity, operation, digest.hex()]
        if (
            self.session.bind is not None
            and self.session.bind.dialect.name == "postgresql"
        ):
            lock_id = int.from_bytes(
                canonical_digest(lock_material)[:8], "big", signed=True
            )
            await self.session.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id}
            )
        record = (
            await self.session.execute(
                select(AdministrativeOperationModel)
                .where(
                    AdministrativeOperationModel.workspace_id == workspace_id,
                    AdministrativeOperationModel.actor == identity,
                    AdministrativeOperationModel.operation == operation,
                    AdministrativeOperationModel.key_digest == digest,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        if record is not None:
            if record.payload_digest != payload_digest:
                raise ConflictError(
                    "Idempotency key is already bound to another payload"
                )
            expires = record.expires_at.replace(tzinfo=record.expires_at.tzinfo or UTC)
            if expires <= now or record.response_ciphertext is None:
                raise ConflictError(
                    "Idempotency replay retention expired; reconcile the resource before starting another operation"
                )
            response = json.loads(
                decrypt_secret(record.response_ciphertext, self.encryption_key)
            )
            response["idempotency_replayed"] = True
            return response
        self.record = AdministrativeOperationModel(
            workspace_id=workspace_id,
            actor=identity,
            operation=operation,
            key_digest=digest,
            payload_digest=payload_digest,
            expires_at=now + timedelta(hours=24),
        )
        self.session.add(self.record)
        await self.session.flush()
        return None

    async def save(self, response: dict[str, Any]) -> None:
        if self.record is not None:
            encoded = json.dumps(
                response, sort_keys=True, separators=(",", ":"), default=str
            )
            if len(encoded.encode()) > 1024 * 1024:
                raise ValidationError("Idempotent response exceeds the retention limit")
            self.record.response_ciphertext = encrypt_secret(
                encoded, self.encryption_key
            )
            await self.session.flush()

    async def purge_expired_secrets(self) -> int:
        result = await self.session.execute(
            update(AdministrativeOperationModel)
            .where(
                AdministrativeOperationModel.expires_at <= datetime.now(UTC),
                AdministrativeOperationModel.response_ciphertext.is_not(None),
            )
            .values(response_ciphertext=None)
        )
        return result.rowcount
