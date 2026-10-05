from shared.security.api_keys import (
    issue_control_api_key,
    parse_project_api_key,
)


def test_control_key_uses_dedicated_namespace() -> None:
    issued = issue_control_api_key()

    assert issued.value.startswith("woobe_control_")
    assert issued.kind == "control"
    assert issued.environment is None

    parsed = parse_project_api_key(issued.value)

    assert parsed is not None
    assert parsed.kind == "control"
    assert parsed.environment is None
    assert parsed.public_prefix == issued.public_prefix
    assert parsed.matches_binding(kind="control", environment=None)
