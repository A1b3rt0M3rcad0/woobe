from datetime import UTC, datetime, timedelta
from hashlib import sha256
import io
import json
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.package.domain.errors import PackageError
from modules.package.infra.artifact_repository import PackageArtifactRepository
from modules.package.infra.artifact_storage import LocalPackageArtifactStorage
from modules.package.infra.bundles import snapshot_directory
from modules.package.infra.models import PackageUploadModel
from shared.infra.database.base import Base
from shared.security.principal import AuthenticatedPrincipal


@pytest.mark.asyncio
async def test_upload_survives_service_recreation_and_revalidates_private_durable_bytes(
    tmp_path, monkeypatch
):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"package": None}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync, tables=[PackageUploadModel.__table__]
            )
        )
    monkeypatch.setattr(
        "modules.package.infra.artifact_repository.authorize_phase", AsyncMock()
    )
    root = tmp_path / "source"
    root.mkdir()
    docs = {
        "woobe.yaml": {
            "kind": "Package",
            "metadata": {"name": "Support", "version": "1.0.0"},
            "spec": {
                "entrypoint": {"kind": "Agent", "ref": "support"},
                "resources": ["agent.yaml", "model.yaml"],
                "requires": {
                    "credentials": [{"ref": "primary", "provider": "openai_compatible"}]
                },
            },
        },
        "agent.yaml": {
            "kind": "Agent",
            "metadata": {"key": "support", "name": "Support"},
            "spec": {
                "legacy_system_prompt": "Help",
                "model": {"primary": {"ref": "model"}},
            },
        },
        "model.yaml": {
            "kind": "Model",
            "metadata": {"key": "model", "name": "Model"},
            "spec": {
                "provider": "openai_compatible",
                "model": "fake",
                "credential": {"ref": "primary"},
            },
        },
    }
    for name, doc in docs.items():
        (root / name).write_text(
            json.dumps({"format": "woobe-package", "schema_version": "1.0", **doc})
        )
    stream = io.BytesIO()
    with snapshot_directory(root) as bundle:
        digest = bundle.artifact_digest
        bundle.archive(stream)
    stream.seek(0)
    principal = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    project = uuid4()
    storage = LocalPackageArtifactStorage(tmp_path / "persistent")
    repo = PackageArtifactRepository(factory, storage)
    response = await repo.upload(project_id=project, principal=principal, stream=stream)
    assert response["artifact_digest"] == digest
    assert "storage_key" not in response
    recreated = PackageArtifactRepository(
        factory, LocalPackageArtifactStorage(tmp_path / "persistent")
    )
    record = await recreated.get_record(
        project_id=project,
        principal=principal,
        upload_id=UUID(response["upload_id"]),
    )
    with recreated.capture_record(record) as captured:
        assert captured.artifact_digest == digest
        assert (
            captured.graph.components["support"]["spec"]["legacy_system_prompt"]
            == "Help"
        )
    with pytest.raises(PackageError) as caught:
        await recreated.get(
            project_id=uuid4(), principal=principal, upload_id=record.id
        )
    assert caught.value.code == "PACKAGE_UPLOAD_NOT_FOUND"
    async with factory.begin() as session:
        changed = await session.get(PackageUploadModel, record.id)
        changed.artifact_digest = sha256(b"changed").hexdigest()
    record = await recreated.get_record(
        project_id=project, principal=principal, upload_id=record.id
    )
    with pytest.raises(PackageError) as caught:
        recreated.capture_record(record)
    assert caught.value.code == "PACKAGE_ARTIFACT_CHANGED"
    await engine.dispose()
