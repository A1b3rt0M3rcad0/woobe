from dataclasses import replace

import pytest

from modules.agent.application.execution_strategy_registry import (
    build_execution_strategy_registry,
)
from modules.agent.application.knowledge_strategy_registry import (
    build_knowledge_strategy_registry,
)
from modules.agent.application.strategy_configuration import (
    validate_strategy_configuration,
)
from shared.contracts.errors import ValidationError


@pytest.mark.parametrize("kind", ["execution", "knowledge"])
def test_native_strategies_advertise_versioned_config_and_reject_ignored_fields(kind):
    registry = (
        build_execution_strategy_registry()
        if kind == "execution"
        else build_knowledge_strategy_registry()
    )
    descriptor = registry.current_default()
    public = descriptor.as_dict()
    assert public["config_schema_version"] == "1"
    assert public["config_schema"]["additionalProperties"] is False
    assert validate_strategy_configuration(descriptor, {}, schema_version="1") == {}
    with pytest.raises(ValidationError):
        validate_strategy_configuration(
            descriptor, {"silently_ignored": True}, schema_version="1"
        )
    with pytest.raises(ValidationError):
        validate_strategy_configuration(descriptor, {}, schema_version="2")
    public["config_schema"]["additionalProperties"] = True
    assert descriptor.config_schema["additionalProperties"] is False


def test_extension_configuration_is_owned_by_registered_descriptor_and_version():
    descriptor = build_execution_strategy_registry().current_default()
    extension = replace(
        descriptor,
        name="standard",
        config_schema_version="custom-1",
        config_schema={
            "type": "object",
            "properties": {"rounds": {"type": "integer", "minimum": 1, "maximum": 3}},
            "required": ["rounds"],
            "additionalProperties": False,
        },
    )
    assert validate_strategy_configuration(
        extension, {"rounds": 2}, schema_version="custom-1"
    ) == {"rounds": 2}
    for invalid in [{"rounds": 9}, {"rounds": "2"}, {"rounds": True}, {}]:
        with pytest.raises(ValidationError):
            validate_strategy_configuration(
                extension, invalid, schema_version="custom-1"
            )


def test_strategy_schema_resolution_never_fetches_remote_documents():
    descriptor = build_execution_strategy_registry().current_default()
    external = replace(
        descriptor, config_schema={"$ref": "https://untrusted.invalid/schema"}
    )
    with pytest.raises(ValidationError, match="cannot be resolved"):
        validate_strategy_configuration(external, {}, schema_version="1")
