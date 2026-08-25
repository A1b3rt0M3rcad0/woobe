from uuid import uuid4

import pytest

from shared.infra.errors import ValidationError
from shared.runtime_environment import (
    RuntimeEnvironmentDisabledError,
    normalize_runtime_environment,
)


def test_runtime_environment_aliases_are_normalized() -> None:
    assert normalize_runtime_environment("playground") == "draft"
    assert normalize_runtime_environment("release") == "production"
    assert normalize_runtime_environment("staging") == "staging"


def test_runtime_environment_rejects_unknown_values() -> None:
    with pytest.raises(ValidationError, match="Unsupported runtime environment"):
        normalize_runtime_environment("preview")


def test_disabled_error_exposes_operational_context() -> None:
    target_id = uuid4()
    error = RuntimeEnvironmentDisabledError(
        target_type="network",
        target_id=target_id,
        environment="production",
    )

    assert error.code == "RUNTIME_ENVIRONMENT_DISABLED"
    assert error.target_type == "network"
    assert error.target_id == target_id
    assert error.environment == "production"
    assert "production" in str(error)
