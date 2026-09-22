from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.application.dtos.runtime_dtos import AskInput


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


def test_public_run_external_context_maps_to_agent_ask_input() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    payload = PublicRunRequest(
        message="Consulte meus pedidos",
        external_context={"customer_id": "customer-123"},
    )

    input_dto = AskInput(
        **payload.model_dump(exclude={"metadata"}),
        metadata=payload.metadata,
        project_id=project_id,
        agent_id=agent_id,
        execution_context="production",
    )

    assert input_dto.external_context == {"customer_id": "customer-123"}
