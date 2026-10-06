from datetime import UTC, datetime, timedelta
import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from modules.package.domain.errors import PackageError
from modules.package.infra.models import (
    PackageOperationModel,
    PackagePlanModel,
    PackageUploadModel,
)
from modules.package.infra.operation_repository import PackageOperationRepository
from shared.infra.admin_idempotency import principal_identity
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.security.principal import AuthenticatedPrincipal


@pytest.mark.asyncio
async def test_postgres_concurrent_acceptance_uses_one_operation_and_retains_conflict_tombstone(
    monkeypatch,
):
    settings = Settings()
    assert settings.environment == "test", (
        "This qualification requires an isolated test environment"
    )
    engine = create_engine(settings)
    assert engine.dialect.name == "postgresql", "This qualification requires PostgreSQL"
    factory = create_session_factory(engine)
    monkeypatch.setattr(
        "modules.package.infra.operation_repository.authorize_phase", AsyncMock()
    )
    now, project, upload_id, plan_id = datetime.now(UTC), uuid4(), uuid4(), uuid4()
    principal = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    repo = PackageOperationRepository(
        factory, encryption_key=settings.encryption_key, plan_validator=AsyncMock()
    )
    try:
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
                        "required_permissions": ["agent:write"],
                        "effects": [{"key": "agent:create"}],
                    },
                    expires_at=now + timedelta(minutes=5),
                )
            )
        key = "concurrent-" + str(uuid4())
        payload = {
            "plan_id": str(plan_id),
            "plan_digest": "b" * 64,
            "upload_id": str(upload_id),
            "artifact_digest": "a" * 64,
            "lifecycle": "draft",
            "bindings": {"secrets": {"service-key": "protected-value"}},
        }
        results = await asyncio.gather(
            *(
                repo.accept(
                    project_id=project, principal=principal, key=key, payload=payload
                )
                for _ in range(8)
            )
        )
        assert len({result.id for result, _ in results}) == 1
        assert sum(not replay for _, replay in results) == 1
        async with factory() as session:
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(PackageOperationModel)
                    .where(PackageOperationModel.project_id == project)
                )
                == 1
            )
        recovered = await repo.lookup(project_id=project, principal=principal, key=key)
        assert recovered.id == results[0][0].id
        changed = dict(
            payload, bindings={"secrets": {"service-key": "different-value"}}
        )
        with pytest.raises(PackageError) as conflict:
            await repo.accept(
                project_id=project, principal=principal, key=key, payload=changed
            )
        assert conflict.value.code == "PACKAGE_IDEMPOTENCY_CONFLICT"
        claims = await asyncio.gather(
            *(repo.claim(project_id=project) for _ in range(8))
        )
        ours = [
            claim
            for claim in claims
            if claim is not None and claim.project_id == project
        ]
        assert len(ours) == 1
        await repo.cancel(
            project_id=project, principal=principal, operation_id=recovered.id
        )
        with pytest.raises(PackageError) as fenced:
            await repo.advance(recovered.id, ours[0].lease_token, "materializing")
        assert fenced.value.code == "PACKAGE_OPERATION_FENCED"
    finally:
        async with factory.begin() as session:
            for model in (PackageOperationModel, PackagePlanModel, PackageUploadModel):
                await session.execute(delete(model).where(model.project_id == project))
        await engine.dispose()
