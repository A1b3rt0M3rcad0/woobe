from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import Request

from shared.presentation.contracts import (
    OperationOutcome,
    OperationRequest,
    OperationResult,
)
from shared.security.principal import AuthenticatedPrincipal
from woobe_api.http.shared.adapters import request_adapter, response_adapter


class _Request:
    def __init__(self, body) -> None:
        self._body = body
        issued_at = datetime.now(UTC)
        self.state = SimpleNamespace(
            principal=AuthenticatedPrincipal(
                user_id=uuid4(),
                session_id=uuid4(),
                issued_at=issued_at,
                expires_at=issued_at + timedelta(minutes=15),
            )
        )
        self.query_params = {"page": "2"}
        self.path_params = {"project_id": "project-1"}

    async def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.mark.asyncio
async def test_request_adapter_builds_transport_neutral_envelope() -> None:
    captured: OperationRequest | None = None

    async def handler(request: OperationRequest) -> OperationResult:
        nonlocal captured
        captured = request
        return OperationResult(body={"ok": True})

    http_request = _Request({"name": "Woobe"})
    result = await request_adapter(cast(Request, http_request), handler)

    assert result.body == {"ok": True}
    assert captured is not None
    assert captured.principal == http_request.state.principal
    assert captured.body == {"name": "Woobe"}
    assert captured.query_params == {"page": "2"}
    assert captured.path_params == {"project_id": "project-1"}


@pytest.mark.asyncio
async def test_request_adapter_treats_non_json_body_as_absent() -> None:
    async def handler(request: OperationRequest) -> OperationResult:
        return OperationResult(body=request.body)

    result = await request_adapter(
        cast(Request, _Request(ValueError("not JSON"))),
        handler,
    )

    assert result.body is None


@pytest.mark.parametrize(
    ("outcome", "status_code"),
    [
        (OperationOutcome.SUCCESS, 200),
        (OperationOutcome.CREATED, 201),
        (OperationOutcome.ACCEPTED, 202),
        (OperationOutcome.INVALID, 400),
        (OperationOutcome.UNAUTHENTICATED, 401),
        (OperationOutcome.FORBIDDEN, 403),
        (OperationOutcome.NOT_FOUND, 404),
        (OperationOutcome.CONFLICT, 409),
        (OperationOutcome.UNPROCESSABLE, 422),
        (OperationOutcome.FAILURE, 500),
        (OperationOutcome.NOT_IMPLEMENTED, 501),
        (OperationOutcome.UPSTREAM_FAILURE, 502),
    ],
)
def test_response_adapter_maps_semantic_outcomes(
    outcome: OperationOutcome,
    status_code: int,
) -> None:
    response = response_adapter(
        OperationResult(
            outcome=outcome,
            body={"success": outcome == OperationOutcome.SUCCESS},
            metadata={"X-Woobe-Test": "preserved"},
        )
    )

    assert response.status_code == status_code
    assert response.headers["x-woobe-test"] == "preserved"
