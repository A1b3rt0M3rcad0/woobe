from __future__ import annotations

import json

import pytest

from shared.infra.errors import AuthorizationError
from shared.presentation.errors import authorization_handler


@pytest.mark.asyncio
async def test_csrf_authorization_error_has_machine_readable_code() -> None:
    response = await authorization_handler(
        None,
        AuthorizationError("CSRF validation failed"),
    )

    assert response.status_code == 403
    assert json.loads(response.body)["data"] == {"code": "csrf_invalid"}


@pytest.mark.asyncio
async def test_other_authorization_errors_do_not_request_csrf_retry() -> None:
    response = await authorization_handler(
        None,
        AuthorizationError("Permission denied"),
    )

    assert response.status_code == 403
    assert json.loads(response.body)["data"] is None
