from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.package.application.planning import PlanPackageUseCase
from modules.package.domain.bundle import PackageGraph
from modules.package.domain.errors import PackageError
from modules.package.infra.models import PackagePlanModel, PackageUploadModel
from modules.package.infra.plan_repository import PackagePlanRepository
from shared.infra.admin_idempotency import principal_identity
from shared.infra.database.base import Base
from shared.security.principal import AuthenticatedPrincipal


def scenario(tmp_path):
    project, upload = uuid4(), uuid4()
    now = datetime.now(UTC)
    principal = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    bindings = {
        "format": "woobe-package",
        "schema_version": "1.0",
        "kind": "ImportBindings",
        "metadata": {"name": "Destination", "description": ""},
        "spec": {
            "credentials": {"primary": {"credential_id": str(uuid4())}},
            "project_environment": {},
            "secrets": {},
            "knowledge": {},
        },
    }
    graph = PackageGraph(
        {
            "spec": {
                "entrypoint": {"kind": "Agent", "ref": "assistant"},
                "requires": {
                    "credentials": [{"ref": "primary", "provider": "openai_compatible"}]
                },
            }
        },
        {
            "model": {
                "kind": "Model",
                "metadata": {"key": "model"},
                "spec": {
                    "provider": "openai_compatible",
                    "credential": {"ref": "primary"},
                },
            },
            "assistant": {
                "kind": "Agent",
                "metadata": {"key": "assistant"},
                "spec": {
                    "legacy_system_prompt": "Help",
                    "model": {"primary": {"ref": "model"}},
                },
            },
        },
        {"model": "model.yaml", "assistant": "agent.yaml"},
        ("model", "assistant"),
    )
    inspector = SimpleNamespace(
        capabilities=AsyncMock(return_value={"native": "1"}),
        inspect_bindings=AsyncMock(
            return_value={"credentials": {"primary": {"revision": "1"}}}
        ),
        inspect_component=AsyncMock(return_value={"owner_validated": True}),
        authorize=AsyncMock(),
    )
    artifacts = SimpleNamespace(
        get_record=AsyncMock(return_value=SimpleNamespace(artifact_digest="a" * 64)),
        capture_record=Mock(
            return_value=SimpleNamespace(graph=graph, root=Path(tmp_path), close=Mock())
        ),
    )
    return project, upload, principal, bindings, graph, inspector, artifacts


@pytest.mark.asyncio
async def test_plan_persists_native_pins_and_acceptance_rechecks_without_storage(
    tmp_path, monkeypatch
):
    project, upload, principal, bindings, graph, inspector, artifacts = scenario(
        tmp_path
    )
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"package": None}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync, tables=[PackagePlanModel.__table__, PackageUploadModel.__table__]
            )
        )
    monkeypatch.setattr(
        "modules.package.infra.plan_repository.authorize_phase", AsyncMock()
    )
    async with factory.begin() as session:
        session.add(
            PackageUploadModel(
                id=upload,
                project_id=project,
                actor=principal_identity(principal),
                artifact_digest="a" * 64,
                storage_key="private",
                manifest={},
                inventory=[],
                size_bytes=1,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
    repository = PackagePlanRepository(factory, artifacts, inspector)
    response = await repository.create(
        project_id=project,
        principal=principal,
        upload_id=upload,
        artifact_digest="a" * 64,
        bindings=bindings,
        lifecycle="draft",
        release_notes=None,
        reason=None,
        api_origin="https://api.woobe.test",
    )
    assert response["api_origin"] == "https://api.woobe.test"
    assert "source_definition" not in response and "inspections" not in response
    artifacts.capture_record.return_value.close.assert_called_once()
    from uuid import UUID

    async with factory() as session:
        record = await session.get(PackagePlanModel, UUID(response["plan_id"]))
        payload = {
            "bindings": bindings,
            "release_notes": None,
            "reason": None,
            "protected_bindings": {},
        }
        artifacts.capture_record.reset_mock()
        await repository.validate_acceptance(
            session, record, payload, principal=principal
        )
        artifacts.capture_record.assert_not_called()
        inspector.inspect_bindings.return_value = {
            "credentials": {"primary": {"revision": "2"}}
        }
        with pytest.raises(PackageError) as caught:
            await repository.validate_acceptance(
                session, record, payload, principal=principal
            )
        assert caught.value.code == "PACKAGE_BINDINGS_CHANGED"
    await engine.dispose()


@pytest.mark.asyncio
async def test_protected_values_are_never_part_of_plan_but_are_exactly_required_on_apply(
    tmp_path,
):
    project, upload, principal, bindings, graph, inspector, artifacts = scenario(
        tmp_path
    )
    bindings["spec"]["credentials"]["primary"] = {"protected_ref": "new-provider-key"}
    approved = await PlanPackageUseCase(inspector).execute(
        project_id=project,
        principal=principal,
        graph=graph,
        support={},
        artifact_digest="a" * 64,
        upload_id=upload,
        bindings=bindings,
        lifecycle="draft",
        api_origin="https://api.woobe.test",
    )
    repository = PackagePlanRepository(None, artifacts, inspector)
    record = SimpleNamespace(document=approved.document, project_id=project)
    for protected in ({}, {"extra": "value"}, {"new-provider-key": ""}):
        with pytest.raises(PackageError) as caught:
            await repository.validate_acceptance(
                None,
                record,
                {
                    "bindings": bindings,
                    "release_notes": None,
                    "reason": None,
                    "protected_bindings": protected,
                },
                principal=principal,
            )
        assert caught.value.code == "PACKAGE_PROTECTED_BINDINGS_INVALID"
    await repository.validate_acceptance(
        None,
        record,
        {
            "bindings": bindings,
            "release_notes": None,
            "reason": None,
            "protected_bindings": {
                "new-provider-key": "private-value-never-saved-in-plan"
            },
        },
        principal=principal,
    )
    assert "private-value-never-saved-in-plan" not in str(approved.document)
