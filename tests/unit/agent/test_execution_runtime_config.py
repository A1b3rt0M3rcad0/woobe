import pytest

from modules.agent.application.execution_runtime_config import (
    DEFAULT_INTERMEDIATE_MESSAGES_ENABLED,
    canonicalize_execution_runtime_config,
    intermediate_messages_enabled_from_runtime_config,
)
from shared.contracts.errors import ValidationError


def test_historical_runtime_config_is_final_only() -> None:
    assert DEFAULT_INTERMEDIATE_MESSAGES_ENABLED is False
    assert intermediate_messages_enabled_from_runtime_config(None) is False
    assert intermediate_messages_enabled_from_runtime_config({}) is False
    assert intermediate_messages_enabled_from_runtime_config(
        {"execution_strategy": "standard"}
    ) is False


def test_execution_runtime_config_reads_explicit_intermediate_policy() -> None:
    assert intermediate_messages_enabled_from_runtime_config(
        {"execution": {"intermediate_messages": True}}
    ) is True
    assert intermediate_messages_enabled_from_runtime_config(
        {"execution": {"intermediate_messages": False}}
    ) is False


def test_execution_runtime_config_preserves_other_runtime_fields() -> None:
    raw = {
        "execution_strategy": "scientific_method",
        "execution": {
            "intermediate_messages": True,
            "future_setting": {"enabled": True},
        },
        "tools": {"tool_ids": []},
    }

    normalized = canonicalize_execution_runtime_config(raw)

    assert normalized == raw
    assert normalized is not raw
    assert normalized["execution"] is not raw["execution"]


@pytest.mark.parametrize(
    "value",
    [
        {"execution": "enabled"},
        {"execution": {"intermediate_messages": "yes"}},
        {"execution": {"intermediate_messages": 1}},
    ],
)
def test_execution_runtime_config_rejects_invalid_policy(value) -> None:
    with pytest.raises(ValidationError):
        canonicalize_execution_runtime_config(value)
