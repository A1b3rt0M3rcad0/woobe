from datetime import UTC, datetime, timedelta
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.package.application.export_projection import (
    ExportProjection,
    reference_requirements,
)
from modules.package.application.requests import ExportPackageRequest
from modules.package.infra.export_repository import PackageExportRepository
from modules.package.infra.artifact_storage import LocalPackageArtifactStorage
from modules.package.infra.models import PackageExportModel
from shared.infra.database.base import Base
from shared.security.principal import AuthenticatedPrincipal
from modules.package.domain.errors import PackageError


@pytest.mark.asyncio
async def test_exports_have_independent_ids_and_scope_rechecks_every_dependency(
    monkeypatch, tmp_path
):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"package": None}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync, tables=[PackageExportModel.__table__]
            )
        )
    authority = AsyncMock()
    monkeypatch.setattr(
        "modules.package.infra.export_repository.authorize_phase", authority
    )
    project, target, credential_id = uuid4(), uuid4(), str(uuid4())
    actor = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    captured = {
        "source": {
            "agent_id": str(target),
            "snapshot_id": str(uuid4()),
            "version": "1.0.0",
            "kind": "draft",
        },
        "definition": {
            "name": "Support",
            "description": "",
            "provider": "custom",
            "model": "fake",
            "provider_credential_id": credential_id,
            "model_spec_snapshot": {"model_id": "fake"},
            "session_mode": "stateless",
            "system_prompt": "Help",
            "runtime_config": {},
        },
        "credentials": {
            credential_id: {
                "provider": "custom",
                "metadata": {"provider_family": "openai"},
            }
        },
        "tools": [],
        "skills": [],
        "artifacts": {},
        "knowledge": None,
    }
    repo = PackageExportRepository(
        sessions,
        LocalPackageArtifactStorage(tmp_path),
        SimpleNamespace(capture=AsyncMock(return_value=[captured])),
        None,
        SimpleNamespace(capture=AsyncMock(return_value={})),
        projection_factory=ExportProjection,
        reference_collector=reference_requirements,
    )
    request = ExportPackageRequest(
        kind="Agent",
        target_id=str(target),
        source="draft",
        name="Support",
        version="1.0.0",
    )
    first = await repo.create(project_id=project, principal=actor, request=request)
    second = await repo.create(project_id=project, principal=actor, request=request)
    assert (
        first["export_id"] != second["export_id"]
        and first["export_id"] != credential_id
    )
    assert (
        first["artifact_digest"] == second["artifact_digest"]
        and first["transport_digest"] == second["transport_digest"]
    )
    authority.reset_mock()
    receipt, content = await repo.capture_artifact(
        project_id=project,
        principal=actor,
        export_id=__import__("uuid").UUID(first["export_id"]),
    )
    assert len(content) == receipt["size_bytes"]
    assert {call.args[3] for call in authority.await_args_list} >= {
        "project:read",
        "agent:read",
        "provider:read",
    }
    assert credential_id not in json.dumps(receipt)
    with pytest.raises(PackageError, match="unavailable"):
        await repo.capture_artifact(
            project_id=uuid4(),
            principal=actor,
            export_id=__import__("uuid").UUID(first["export_id"]),
        )
    await engine.dispose()
