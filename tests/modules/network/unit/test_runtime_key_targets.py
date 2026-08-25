from uuid import uuid4

import pytest
from pydantic import ValidationError

from modules.core.application.dtos.runtime_api_key_dtos import (
    CreateRuntimeApiKeyInput,
)
from modules.core.domain.enums import RuntimeTargetType


def _base() -> dict:
    return {
        "project_id": uuid4(),
        "name": "Runtime",
        "environment": "staging",
        "interfaces": ["http", "stream"],
        "created_by_user_id": uuid4(),
    }


def test_legacy_agent_binding_is_normalized() -> None:
    agent_id = uuid4()
    value = CreateRuntimeApiKeyInput(**_base(), agent_id=agent_id)

    assert value.target_type == RuntimeTargetType.agent
    assert value.target_id == agent_id
    assert value.agent_id == agent_id


def test_network_binding_does_not_populate_agent_id() -> None:
    network_id = uuid4()
    value = CreateRuntimeApiKeyInput(
        **_base(),
        target_type="network",
        target_id=network_id,
    )

    assert value.target_type == RuntimeTargetType.network
    assert value.target_id == network_id
    assert value.agent_id is None


def test_network_binding_rejects_legacy_agent_id() -> None:
    with pytest.raises(ValidationError):
        CreateRuntimeApiKeyInput(
            **_base(),
            target_type="network",
            target_id=uuid4(),
            agent_id=uuid4(),
        )
