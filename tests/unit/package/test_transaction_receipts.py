from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from modules.package.domain.errors import PackageError
from modules.package.infra.models import (
    PackageEffectModel,
    PackageOperationModel,
    PackagePlanModel,
)
from modules.package.infra.receipts import PackageTransactionReceipt
from shared.contracts.unit_of_work import UnitOfWork
from shared.infra.admin_idempotency import principal_identity
from shared.infra.database.base import Base
from shared.infra.transactional_handler import TransactionalHandler
from shared.presentation.contracts import (
    OperationOutcome,
    OperationRequest,
    OperationResult,
)
from shared.security.principal import AuthenticatedPrincipal


class ExampleResource(Base):
    __tablename__ = "package_receipt_test_resources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)


class ExampleUnitOfWork(UnitOfWork):
    def __init__(self, factory):
        self.factory = factory

    async def __aenter__(self):
        self.session = self.factory()
        return self

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self.session.close()


@pytest.mark.asyncio
async def test_effect_and_receipt_commit_together_and_replay_after_lost_response(
    monkeypatch,
):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"package": None}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tables = [
        PackageOperationModel.__table__,
        PackageEffectModel.__table__,
        PackagePlanModel.__table__,
        ExampleResource.__table__,
    ]
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(sync, tables=tables)
        )
    authority = AsyncMock()
    monkeypatch.setattr("modules.package.infra.receipts.authorize_phase", authority)
    now = datetime.now(UTC)
    actor = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    operation_id, project_id, lease, plan_id = uuid4(), uuid4(), uuid4(), uuid4()
    async with factory.begin() as session:
        session.add(
            PackagePlanModel(
                id=plan_id,
                project_id=project_id,
                actor=principal_identity(actor),
                upload_id=uuid4(),
                artifact_digest="a" * 64,
                plan_digest="b" * 64,
                document={
                    "effects": [
                        {"key": "agent:create", "permission": "agent:write"},
                        {"key": "agent:update", "permission": "agent:write"},
                    ]
                },
                expires_at=now + timedelta(hours=1),
            )
        )
        session.add(
            PackageOperationModel(
                id=operation_id,
                project_id=project_id,
                actor=principal_identity(actor),
                key_digest=b"key",
                payload_fingerprint=b"private",
                payload_ciphertext="protected",
                principal_ciphertext="protected",
                artifact_digest="a" * 64,
                upload_id=uuid4(),
                plan_id=plan_id,
                lifecycle="draft",
                state="materializing",
                lease_token=lease,
                lease_until=datetime.now(UTC) + timedelta(minutes=5),
                phases_total=2,
            )
        )
    uow = ExampleUnitOfWork(factory)

    async def create(request):
        resource = ExampleResource()
        uow.session.add(resource)
        await uow.session.flush()
        return OperationResult(
            outcome=OperationOutcome.CREATED, body={"data": {"id": resource.id}}
        )

    receipt = PackageTransactionReceipt(
        operation_id=operation_id,
        lease_token=lease,
        phase="agent:create",
        permission="agent:write",
        encryption_key="test-encryption-key",
        evidence={"kind": "Agent", "component": "support", "action": "created"},
    )
    handler = TransactionalHandler(uow, create).with_receipt(receipt)
    request = OperationRequest(principal=actor, body={"project_id": str(project_id)})
    first = await handler(request)
    # The first response can disappear after commit. A new request obtains the exact receipt.
    second = await handler(request)
    assert second == first
    async with factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(ExampleResource)) == 1
        )
        assert (
            await session.scalar(select(func.count()).select_from(PackageEffectModel))
            == 1
        )
        operation = await session.get(PackageOperationModel, operation_id)
        assert operation.phases_completed == 1
        assert operation.inventory[0]["resource_id"] == "1"
    assert authority.await_count == 2
    # Reading a receipt must also reauthorize, rather than bypass a subsequent revocation.
    authority.side_effect = PackageError(
        "PACKAGE_AUTHORITY_REQUIRED", "Authority revoked"
    )
    with pytest.raises(PackageError):
        await handler(request)
    authority.side_effect = None
    wrong_lease = PackageTransactionReceipt(
        operation_id=operation_id,
        lease_token=uuid4(),
        phase="agent:update",
        permission="agent:write",
        encryption_key="test-encryption-key",
    )
    with pytest.raises(PackageError) as caught:
        await TransactionalHandler(uow, create).with_receipt(wrong_lease)(request)
    assert caught.value.code == "PACKAGE_OPERATION_FENCED"
    # A failed receipt write rolls back the owner's resource mutation too.
    failing = PackageTransactionReceipt(
        operation_id=operation_id,
        lease_token=lease,
        phase="agent:update",
        permission="agent:write",
        encryption_key="test-encryption-key",
    )
    failing.save = AsyncMock(side_effect=RuntimeError("storage failure"))
    with pytest.raises(RuntimeError):
        await TransactionalHandler(uow, create).with_receipt(failing)(request)
    async with factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(ExampleResource)) == 1
        )
    await engine.dispose()
