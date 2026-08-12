from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from modules.core.application.dtos.runtime_api_key_dtos import CreateRuntimeApiKeyInput
from modules.core.domain.enums import (
    RuntimeEnvironment,
    RuntimeInterface,
    RuntimeTargetType,
)


def test_runtime_key_rejects_jobs_while_interface_is_coming_soon() -> None:
    with pytest.raises(PydanticValidationError, match="Jobs are coming soon"):
        CreateRuntimeApiKeyInput(
            project_id=uuid4(),
            name="Async integration",
            target_type=RuntimeTargetType.agent,
            target_id=uuid4(),
            environment=RuntimeEnvironment.production,
            interfaces=[RuntimeInterface.http, RuntimeInterface.jobs],
            created_by_user_id=uuid4(),
        )


def test_network_runtime_key_keeps_network_target_without_agent_alias() -> None:
    network_id = uuid4()

    payload = CreateRuntimeApiKeyInput(
        project_id=uuid4(),
        name="Network production",
        target_type=RuntimeTargetType.network,
        target_id=network_id,
        environment=RuntimeEnvironment.production,
        interfaces=[RuntimeInterface.http, RuntimeInterface.stream],
        created_by_user_id=uuid4(),
    )

    assert payload.target_type == RuntimeTargetType.network
    assert payload.target_id == network_id
    assert payload.agent_id is None
    assert payload.interfaces == [RuntimeInterface.http, RuntimeInterface.stream]
