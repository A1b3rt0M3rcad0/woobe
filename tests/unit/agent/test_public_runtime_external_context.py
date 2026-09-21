from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest


def test_public_run_request_accepts_external_context() -> None:
    request = PublicRunRequest(
        message="Olá",
        external_context={
            "customer_id": "customer-123",
            "language": "pt-BR",
        },
    )

    assert request.external_context == {
        "customer_id": "customer-123",
        "language": "pt-BR",
    }


def test_public_run_request_keeps_strict_unknown_field_rejection() -> None:
    with pytest.raises(ValidationError):
        PublicRunRequest(
            message="Olá",
            external_context={"customer_id": "customer-123"},
            unknown_runtime_field=True,
        )
