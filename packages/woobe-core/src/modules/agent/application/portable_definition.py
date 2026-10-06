"""Read-only validation contracts shared by portable import and native composition."""

from modules.agent.application.dtos.behavior_dtos import BehaviorSpecification
from modules.agent.application.dtos.skill_dtos import ImportSkillInput
from modules.agent.application.dtos.tools_dtos import CreateToolInput
from modules.agent.application.execution_strategy_registry import (
    build_execution_strategy_registry,
    list_execution_strategies,
)
from modules.agent.application.knowledge_strategy_registry import (
    build_knowledge_strategy_registry,
    list_knowledge_strategies,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.application.skill_packages import parse_skill_package
from modules.agent.application.strategy_configuration import (
    validate_strategy_configuration,
)
from modules.agent.domain.external_context_contract import (
    normalize_external_context_contract,
)
from modules.agent.domain.enums import Provider
from shared.contracts.errors import ValidationError


def portable_definition_capabilities():
    return {
        "execution_strategies": list_execution_strategies(),
        "knowledge_strategies": list_knowledge_strategies(),
        "context_managers": ["stdcm"],
        "providers": [item.value for item in Provider],
        "skill_resource_max_bytes": 200_000,
        "skill_package_max_bytes": 1_000_000,
    }


def inspect_portable_agent(spec: dict) -> dict:
    execution = spec.get("execution", {})
    descriptor = build_execution_strategy_registry().get(
        execution.get("strategy", "standard")
    )
    execution_config = validate_strategy_configuration(
        descriptor,
        execution.get("config", {}),
        schema_version=execution.get("config_schema_version", "1"),
    )
    context = spec.get("context", {})
    if context.get("manager", {}).get("name", "stdcm") != "stdcm":
        raise ValidationError("Unsupported Context Manager")
    policy = ContextPolicyV1.model_validate(context.get("policy", {}))
    knowledge = spec.get("knowledge")
    knowledge_config = None
    if knowledge is not None:
        registered = build_knowledge_strategy_registry().describe(
            knowledge.get("strategy", "rag")
        )
        knowledge_config = validate_strategy_configuration(
            registered,
            knowledge.get("strategy_config", {}),
            schema_version=knowledge.get("strategy_config_schema_version", "1"),
        )
    if spec.get("behavior") is not None:
        BehaviorSpecification.model_validate(spec["behavior"])
    external_context = normalize_external_context_contract(
        spec.get("external_context", {})
    )
    return {
        "execution_strategy": descriptor.name,
        "execution_config": execution_config,
        "knowledge_config": knowledge_config,
        "context_policy": policy.model_dump(mode="json"),
        "external_context_contract": external_context,
    }


def inspect_portable_skill(
    *, version: str, skill_md: str, resources: dict[str, str], required_tools: list[str]
) -> dict:
    return parse_skill_package(
        ImportSkillInput(
            version=version,
            skill_md=skill_md,
            resources=resources,
            required_tools=required_tools,
        )
    )


def inspect_portable_tool(*, project_id, metadata: dict, spec: dict) -> dict:
    native = CreateToolInput.model_validate(
        {
            "project_id": project_id,
            "name": metadata["name"],
            **{
                key: value
                for key, value in spec.items()
                if key
                in {
                    "type",
                    "description",
                    "config",
                    "input_schema",
                    "output_schema",
                    "timeout_ms",
                }
            },
            "risk_level": spec.get("risk") or "low",
        }
    )
    return {
        "create_input": native.model_dump(mode="json"),
        "binding_permission": spec.get("permission", "allow"),
        "mcp_permissions": spec.get("permissions", []),
    }
