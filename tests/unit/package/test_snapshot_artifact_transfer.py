"""Retained artifact transfer validates a real closure and bounded deterministic bytes."""
from hashlib import sha256
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.package.application.asac_definition import portable_definition
from modules.package.domain.errors import PackageError
from modules.package.infra.bundles import receive_archive, snapshot_directory
from modules.package.infra.snapshot_artifact_repository import PackageSnapshotArtifactRepository


@pytest.mark.asyncio
async def test_transfer_roundtrip_is_deterministic_and_reports_missing_object(tmp_path):
    fixture = json.loads((Path(__file__).parents[3] / "specs/package/v1/fixtures/complete.json").read_text())
    for name, content in fixture["files"].items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    repository = PackageSnapshotArtifactRepository(None, None, None)
    repository.capture = AsyncMock(side_effect=lambda **kwargs: snapshot_directory(tmp_path))
    args = {"project_id": uuid4(), "principal": object(), "artifact_id": uuid4()}
    receipt, content = await repository.transfer(**args)
    again, repeated = await repository.transfer(**args)
    assert receipt == again and content == repeated
    assert receipt["transport_digest"] == sha256(content).hexdigest()
    assert receipt["size_bytes"] == len(content)
    with receive_archive(io.BytesIO(content), locked=True) as bundle:
        definition, _ = portable_definition(bundle)
        assert definition == receipt["definition_digest"]
        assert "sha256:" + bundle.artifact_digest == receipt["artifact_digest"]
        assert bundle.inventory == receipt["inventory"]
    repository.capture.side_effect = FileNotFoundError("private storage path")
    with pytest.raises(PackageError, match="metadata exists but its executable object is unavailable") as failure:
        await repository.transfer(**args)
    assert failure.value.code == "ASAC_OBJECT_UNAVAILABLE"
    assert "private storage path" not in str(failure.value)
