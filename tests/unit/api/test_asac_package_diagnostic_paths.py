import json
from types import SimpleNamespace as N
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from starlette.requests import Request

from modules.package.domain.errors import PackageError
from woobe_api.http.shared import asac_draft_routes as module


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["Agent", "Network"])
async def test_stage_transport_retains_component_file_and_path(monkeypatch, kind):
    error = PackageError(
        "ASAC_CANDIDATE_BINDING_UNAVAILABLE",
        "Accepted native identity missing",
        file="agents/support.yaml",
        path="/metadata/key",
    )
    candidate = N(stage=AsyncMock(side_effect=error))
    monkeypatch.setattr(module, "build_snapshot_artifacts", lambda: object())
    monkeypatch.setattr(module, "build_candidate_preparation", lambda: object())
    router = module.draft_router(
        "/asac", lambda **_: object(), kind, candidate_builder=lambda **_: candidate
    )
    endpoint = next(
        route.endpoint for route in router.routes if route.path == "/asac/candidates"
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/asac/candidates",
            "scheme": "http",
            "server": ("localhost", 8000),
            "headers": [],
            "state": {"principal": object()},
        }
    )
    response = await endpoint(
        project_id=uuid4(), resource_id=uuid4(), body=object(), request=request
    )
    assert response.status_code == 422
    assert json.loads(response.body)["data"]["diagnostics"] == [error.as_dict()]
