from copy import deepcopy
import re

from modules.agent.application.portable_definition import inspect_portable_tool
from modules.agent.domain.tool_project_environment import (
    _PROJECT_ENV_TEMPLATE_PATTERN,
    collect_tool_project_environment_keys,
)
from shared.contracts.errors import ValidationError

_SECRET_PATTERN = re.compile(r"\{\{secret:([^}]+)\}\}")


def compile_imported_tool_inputs(*, project_id, metadata, spec, environment, secrets):
    """Remap native references, never protected values, before native compilation."""
    source = deepcopy(spec)
    config = source["config"]
    referenced = collect_tool_project_environment_keys(
        [config, source.get("permissions", [])]
    )
    if referenced - set(environment):
        raise ValidationError(
            "Tool references undeclared Project Environment requirements"
        )

    def secret_name(name):
        if name not in secrets:
            raise ValidationError("Tool references an undeclared Secret requirement")
        return secrets[name]

    def rewrite(value):
        if isinstance(value, str):
            result = _PROJECT_ENV_TEMPLATE_PATTERN.sub(
                lambda match: "{{ project_env." + environment[match[1]] + " }}", value
            )
            return _SECRET_PATTERN.sub(
                lambda match: "{{secret:" + secret_name(match[1].strip()) + "}}", result
            )
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, dict):
            result = {key: rewrite(item) for key, item in value.items()}
            if result.get("kind") == "project_environment" and "field" in result:
                result["field"] = environment[value["field"]]
            if isinstance(result.get("auth"), dict) and isinstance(
                result["auth"].get("credentials"), list
            ):
                result["auth"]["credentials"] = [
                    secret_name(name) for name in value["auth"]["credentials"]
                ]
            if isinstance(result.get("env_secret_refs"), dict):
                result["env_secret_refs"] = {
                    key: secret_name(name)
                    for key, name in value["env_secret_refs"].items()
                }
            return result
        return value

    source["config"] = rewrite(config)
    # Carry desired bindings in author-only remote-name intent, never cached schemas.
    desired = []
    for permission in source.get("permissions", []):
        desired.append(
            {**permission, "bindings": rewrite(permission.get("bindings", {}))}
        )
    source["permissions"] = desired
    permission = deepcopy(source["config"].get("permission") or {})
    if (
        "permission" in source
        and "mode" in permission
        and source["permission"] != permission["mode"]
    ):
        raise ValidationError("Portable Tool permission declarations conflict")
    if (
        source.get("risk")
        and permission.get("risk_level")
        and source["risk"] != permission["risk_level"]
    ):
        raise ValidationError("Portable Tool risk declarations conflict")
    permission["mode"] = source.get("permission", permission.get("mode", "allow"))
    if source.get("risk"):
        permission["risk_level"] = source["risk"]
    source["config"]["permission"] = permission
    return inspect_portable_tool(project_id=project_id, metadata=metadata, spec=source)[
        "create_input"
    ]
