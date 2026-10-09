import json
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.package.application.requests import ExportPackageRequest
from modules.package.domain.errors import PackageError
from modules.package.infra.export_repository import PackageExportRepository
from shared.contracts.errors import (
    ConflictError,
    SnapshotCaptureConflict,
    AuthorizationError,
)
from woobe_api.http.package.routes import failure


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,code,path",
    [
        (
            SnapshotCaptureConflict(
                "PACKAGE_EXPORT_NETWORK_BINDING",
                "Pinned snapshot unavailable",
                path="/spec/nodes/0/binding",
            ),
            "PACKAGE_EXPORT_NETWORK_BINDING",
            "/spec/nodes/0/binding",
        ),
        (
            ConflictError("private-provider-value"),
            "PACKAGE_EXPORT_NETWORK_CONFLICT",
            "/spec",
        ),
    ],
)
async def test_network_export_returns_safe_machine_conflict(error, code, path):
    repository = PackageExportRepository(
        None,
        None,
        None,
        N(capture=AsyncMock(side_effect=error)),
        None,
        projection_factory=None,
        reference_collector=None,
    )
    with pytest.raises(PackageError) as caught:
        await repository.create(
            project_id=uuid4(),
            principal=object(),
            request=ExportPackageRequest(kind="Network", target_id=str(uuid4())),
        )
    diagnostic = caught.value.as_dict()
    assert (
        diagnostic["code"] == code
        and diagnostic["path"] == path
        and diagnostic["file"] == "network.yaml"
    )
    response = failure(caught.value)
    assert response.status_code == 409
    data = json.loads(response.body)
    assert data["data"]["diagnostics"][0] == diagnostic
    assert b"private-provider" not in response.body


@pytest.mark.asyncio
async def test_network_export_does_not_convert_authorization_denials_to_capture_conflicts():
    repository = PackageExportRepository(
        None,
        None,
        None,
        N(capture=AsyncMock(side_effect=AuthorizationError("denied"))),
        None,
        projection_factory=None,
        reference_collector=None,
    )
    with pytest.raises(AuthorizationError):
        await repository.create(
            project_id=uuid4(),
            principal=object(),
            request=ExportPackageRequest(kind="Network", target_id=str(uuid4())),
        )


@pytest.mark.asyncio
async def test_incomplete_pinned_agent_model_preserves_safe_inspection_path():
    repository = PackageExportRepository(
        None,
        None,
        N(
            capture=AsyncMock(
                side_effect=SnapshotCaptureConflict(
                    "PACKAGE_EXPORT_INCOMPLETE",
                    "Snapshot has no complete ModelSpec",
                    path="/spec/model/primary",
                )
            )
        ),
        None,
        None,
        projection_factory=None,
        reference_collector=None,
    )
    with pytest.raises(PackageError) as caught:
        await repository.create(
            project_id=uuid4(),
            principal=object(),
            request=ExportPackageRequest(
                kind="Agent",
                target_id=str(uuid4()),
                source="release",
                release_version="1.0.0",
            ),
        )
    diagnostic = caught.value.as_dict()
    assert diagnostic["file"] == "agent.yaml"
    assert diagnostic["path"] == "/spec/model/primary"
    assert failure(caught.value).status_code == 422
