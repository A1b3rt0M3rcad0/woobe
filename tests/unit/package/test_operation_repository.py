from datetime import UTC, datetime, timedelta
import json
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.package.domain.errors import PackageError
from modules.package.domain.operations import operation_status
from modules.package.infra.models import (
    PackageOperationModel,
    PackagePlanModel,
    PackageUploadModel,
)
from modules.package.infra.operation_repository import (
    PackageOperationRepository,
    decode_principal,
)
from shared.infra.admin_idempotency import principal_identity
from shared.infra.database.base import Base
from shared.security.principal import AuthenticatedPrincipal


@pytest.mark.asyncio
async def test_acceptance_pins_protected_payload_and_reconciles_after_plan_expiry(
    monkeypatch,
):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"package": None}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync,
                tables=[
                    model.__table__
                    for model in (
                        PackageUploadModel,
                        PackagePlanModel,
                        PackageOperationModel,
                    )
                ],
            )
        )
    authority, validator = AsyncMock(), AsyncMock()
    monkeypatch.setattr(
        "modules.package.infra.operation_repository.authorize_phase", authority
    )
    repo = PackageOperationRepository(
        factory, encryption_key="private-server-key", plan_validator=validator
    )
    now, project, upload_id, plan_id = datetime.now(UTC), uuid4(), uuid4(), uuid4()
    principal = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    async with factory.begin() as session:
        session.add(
            PackageUploadModel(
                id=upload_id,
                project_id=project,
                actor=principal_identity(principal),
                artifact_digest="a" * 64,
                storage_key="packages/private",
                manifest={},
                inventory=[],
                size_bytes=1,
                expires_at=now + timedelta(hours=1),
            )
        )
        session.add(
            PackagePlanModel(
                id=plan_id,
                project_id=project,
                actor=principal_identity(principal),
                upload_id=upload_id,
                artifact_digest="a" * 64,
                plan_digest="b" * 64,
                document={
                    "lifecycle": "draft",
                    "required_permissions": ["agent:write", "tool:write"],
                    "effects": [{"key": "agent:create"}],
                },
                expires_at=now + timedelta(minutes=5),
            )
        )
    payload = {
        "plan_id": str(plan_id),
        "plan_digest": "b" * 64,
        "upload_id": str(upload_id),
        "artifact_digest": "a" * 64,
        "lifecycle": "draft",
        "bindings": {"secrets": {"service-key": "do-not-expose-value"}},
    }
    first, replayed = await repo.accept(
        project_id=project, principal=principal, key="lost-response", payload=payload
    )
    assert not replayed
    assert "do-not-expose-value" not in first.payload_ciphertext
    assert (
        decode_principal(first.principal_ciphertext, "private-server-key") == principal
    )
    assert "do-not-expose-value" not in json.dumps(operation_status(first))
    assert operation_status(first)["lifecycle_state"] is None
    # Existing acceptance remains recoverable after its temporary plan expires.
    async with factory.begin() as session:
        plan = await session.get(PackagePlanModel, plan_id)
        plan.expires_at = now - timedelta(seconds=1)
    second, replayed = await repo.accept(
        project_id=project, principal=principal, key="lost-response", payload=payload
    )
    assert replayed and second.id == first.id
    validator.assert_awaited_once()
    recovered = await repo.lookup(
        project_id=project, principal=principal, key="lost-response"
    )
    assert recovered.id == first.id
    changed = dict(
        payload, bindings={"secrets": {"service-key": "changed-protected-value"}}
    )
    with pytest.raises(PackageError) as conflict:
        await repo.accept(
            project_id=project,
            principal=principal,
            key="lost-response",
            payload=changed,
        )
    assert conflict.value.code == "PACKAGE_IDEMPOTENCY_CONFLICT"
    with pytest.raises(PackageError) as expired:
        await repo.accept(
            project_id=project,
            principal=principal,
            key="different-request",
            payload=payload,
        )
    assert expired.value.code == "PACKAGE_PLAN_EXPIRED"
    claimed = await repo.claim()
    assert claimed.id == first.id and claimed.state == "resolving"
    assert await repo.claim() is None
    cancelled = await repo.cancel(
        project_id=project, principal=principal, operation_id=first.id
    )
    assert cancelled.state == "cancelling"
    with pytest.raises(PackageError) as fenced:
        await repo.advance(first.id, claimed.lease_token, "materializing")
    assert fenced.value.code == "PACKAGE_OPERATION_FENCED"
    cancellation = await repo.claim()
    terminal = await repo.advance(first.id, cancellation.lease_token, "cancelled")
    assert terminal.state == "cancelled"
    assert await repo.claim() is None
    authority.side_effect = PackageError("PACKAGE_AUTHORITY_REQUIRED", "Revoked")
    with pytest.raises(PackageError):
        await repo.lookup(project_id=project, principal=principal, key="lost-response")
    await engine.dispose()
