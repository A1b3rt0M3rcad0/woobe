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
from modules.agent.application.dtos.ai_dtos import CreateProviderModelInput
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
)
from modules.agent.application.interfaces.model_compatibility import (
    ModelExecutionCompatibilityResolver,
    RuntimeCompatibilityRequest,
)
from modules.agent.domain.entities import ProviderCredential
from modules.agent.domain.model_spec import ModelSpec
from modules.agent.domain.model_spec import ModelOperations
from modules.agent.application.dtos.ai_dtos import (
    CreatePromptInput,
    CreateContractInput,
)
from modules.agent.application.dtos.rag_config_dtos import (
    RAGBuildConfig,
    RAGRuntimeConfig,
)
from modules.agent.application.rag.registry import (
    build_rag_strategy_registry,
    UnknownRAGStrategyError,
)
from modules.agent.domain.external_context_contract import (
    compose_external_context_contracts,
)
from uuid import UUID
from uuid import NAMESPACE_URL, uuid5
from types import SimpleNamespace
from modules.agent.application.tool_converter import agent_tools_to_openai_definitions
from modules.agent.application.skill_bindings import (
    AgentSkillBinding,
    validate_skill_context,
)
from modules.agent.domain.skills import skill_package_hash
from shared.contracts.errors import ValidationError


def portable_definition_capabilities():
    return {
        "execution_strategies": list_execution_strategies(),
        "knowledge_strategies": list_knowledge_strategies(),
        "context_managers": ["stdcm"],
        "rag_strategies": [
            build_rag_strategy_registry().describe(name).as_dict()
            for name in build_rag_strategy_registry().names()
        ],
        "providers": [item.value for item in Provider],
        "skill_resource_max_bytes": 200_000,
        "skill_package_max_bytes": 1_000_000,
    }


def inspect_portable_agent(spec: dict, *, model_specs=None) -> dict:
    execution = spec.get("execution", {})
    descriptor = build_execution_strategy_registry().get(
        execution.get("strategy", "standard")
    )
    for model_spec in model_specs or []:
        report = ModelExecutionCompatibilityResolver().resolve(
            RuntimeCompatibilityRequest(
                model=ModelSpec.from_dict(model_spec),
                execution=descriptor.compatibility,
                tools_enabled=bool(spec.get("tools")),
                context_enabled=True,
                knowledge_enabled=spec.get("knowledge") is not None,
            )
        )
        if not report.compatible:
            raise ValidationError(
                "ModelSpec is incompatible with the declared Agent composition"
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
    if knowledge is not None:
        rag = RAGRuntimeConfig.model_validate(knowledge.get("rag", {}))
        try:
            rag_descriptor = build_rag_strategy_registry().describe(rag.strategy)
        except UnknownRAGStrategyError as exc:
            raise ValidationError("Unknown RAG Strategy") from exc
        validate_strategy_configuration(
            rag_descriptor,
            rag.strategy_config,
            schema_version=rag.strategy_config_schema_version,
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


def portable_skill_identity(package):
    return {
        "name": package["name"],
        "required_tools": package["required_tools"],
        "package_hash": skill_package_hash(package),
    }


def inspect_portable_tool(*, project_id, metadata: dict, spec: dict) -> dict:
    from modules.agent.application.portable_authentication import (
        validate_portable_tool_authentication,
    )

    validate_portable_tool_authentication(spec["config"])
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


def inspect_proposed_provider_model(*, project_id, metadata, spec):
    from modules.agent.application.portable_authentication import (
        validate_portable_model_authentication,
    )

    validate_portable_model_authentication(
        spec.get("model_spec_hint"), base_url=spec.get("base_url")
    )
    provider = Provider(spec["provider"])
    credential = ProviderCredential(
        project_id=project_id, provider=provider, id=UUID(int=0)
    )
    input_dto = CreateProviderModelInput(
        project_id=project_id,
        provider_credential_id=credential.id,
        name=metadata["name"],
        model=spec["model"],
        model_type=spec.get("model_type", "language"),
        spec=spec.get("model_spec_hint"),
        metadata={"base_url": spec["base_url"]} if spec.get("base_url") else {},
    )
    model = CreateProviderModelUseCase.prepare_definition(input_dto, credential)
    normalized = ModelSpec.from_dict(model.spec)
    if (
        normalized.provider != provider.value
        or normalized.model_id != model.model
        or normalized.model_type != input_dto.model_type
    ):
        raise ValidationError("ModelSpec identity differs from the proposed Model")
    return {
        "provider": provider.value,
        "model": model.model,
        "model_type": model.model_type,
        "spec": model.spec,
        "spec_hash": model.spec_hash,
        "spec_version": model.spec_version,
        "existing_model_id": None,
    }


def inspect_portable_network_external_context(contracts):
    return compose_external_context_contracts(contracts)


def inspect_portable_agent_capabilities(*, spec, tools, skills):
    native_tools = [
        SimpleNamespace(
            id=uuid5(NAMESPACE_URL, "woobe-package-tool:" + key),
            **definition["create_input"],
        )
        for key, definition in tools.items()
    ]
    definitions = agent_tools_to_openai_definitions(native_tools)
    names = {item["function"]["name"] for item in definitions}
    selected = spec.get("skills", [])
    bindings = [
        AgentSkillBinding(
            skill_id=uuid5(NAMESPACE_URL, "woobe-package-skill:" + item["ref"]),
            skill_version_id=uuid5(
                NAMESPACE_URL,
                "woobe-package-skill-version:" + item["ref"] + ":" + item["version"],
            ),
            enabled=item.get("enabled", True),
        )
        for item in selected
    ]
    if len({item.skill_id for item in bindings}) != len(bindings):
        raise ValidationError(
            "Only one version of each Skill can be installed on an Agent"
        )
    runtime = {
        "context_manager": {"name": "stdcm"},
        "context": spec.get("context", {}).get("policy", {}),
    }
    validate_skill_context(runtime, bindings)
    for item in selected:
        if (
            item.get("enabled", True)
            and set(skills[item["ref"]]["required_tools"]) - names
        ):
            raise ValidationError(
                "Installed Skill requires Tools absent from the Agent capability set"
            )
    return {"tool_capability_names": sorted(names)}


def inspect_portable_knowledge(*, spec, embedding_spec):
    model = ModelSpec.from_dict(embedding_spec)
    if ModelOperations.EMBEDDING_CREATE not in model.operations:
        raise ValidationError(
            "Portable Knowledge requires an embedding-capable ModelSpec"
        )
    build = RAGBuildConfig.model_validate(spec["vector_snapshot"])
    return {
        "document_count": len(spec["documents"]),
        "build_config": build.model_dump(mode="json"),
    }


def inspect_portable_version_definition(*, kind, metadata, spec):
    definition = {
        "project_id": UUID(int=0),
        "agent_id": UUID(int=0),
        "name": metadata["name"],
        **spec,
    }
    if kind == "Contract":
        if definition.get("validation_mode") == "lenient":
            definition["validation_mode"] = "loose"
        normalized = CreateContractInput.model_validate(definition)
    elif kind == "Prompt":
        normalized = CreatePromptInput.model_validate(definition)
    else:
        raise ValidationError("Unknown native version definition")
    return normalized.model_dump(
        mode="json", exclude={"project_id", "agent_id", "created_by"}
    )
