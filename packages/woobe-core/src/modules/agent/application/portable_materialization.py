"""Native Agent input compilation after Package dependencies have been installed."""

from copy import deepcopy

from modules.agent.application.dtos.ai_dtos import CreateAgentInput, CreateReleaseInput
from modules.agent.application.portable_definition import inspect_portable_agent
from modules.agent.application.dtos.behavior_dtos import canonicalize_behavior_spec
from modules.agent.application.system_instruction_assembler import (
    assemble_system_instructions,
)
from modules.agent.application.use_cases.ai_agent_cases import (
    _force_strict_json_settings,
)
from modules.agent.domain.entities import Agent
from shared.contracts.errors import ValidationError


def compile_imported_agent_inputs(
    *, project_id, document, definitions, resources, agent_id=None, release_notes=None
):
    metadata, spec = document["metadata"], document["spec"]
    primary_key = spec["model"]["primary"]["ref"]
    primary = resources[primary_key]
    fallback_key = (spec["model"].get("fallback") or {}).get("ref")
    fallback = resources[fallback_key] if fallback_key else None
    inspection = inspect_portable_agent(
        spec, model_specs=[model["spec"] for model in (primary, fallback) if model]
    )
    runtime = {
        "execution_strategy": inspection["execution_strategy"],
        "execution_strategy_config": inspection["execution_config"],
        "execution_strategy_config_schema_version": spec.get("execution", {}).get(
            "config_schema_version", "1"
        ),
        "context_manager": {"name": "stdcm"},
        "context": inspection["context_policy"],
        "knowledge_strategy": (spec.get("knowledge") or {}).get("strategy", "rag"),
        "knowledge_strategy_config": inspection["knowledge_config"] or {},
        "knowledge_strategy_config_schema_version": (spec.get("knowledge") or {}).get(
            "strategy_config_schema_version", "1"
        ),
    }
    tool_ids = [str(resources[item["ref"]]["id"]) for item in spec.get("tools", [])]
    if tool_ids:
        runtime["tools"] = {"tool_ids": tool_ids}
    skills = []
    for binding in spec.get("skills", []):
        version = resources[binding["ref"]]
        if version["version"] != binding["version"]:
            raise ValidationError(
                "Imported Skill version differs from the declared binding"
            )
        skills.append(
            {
                "skill_id": version["skill_id"],
                "skill_version_id": version["id"],
                "enabled": binding.get("enabled", True),
            }
        )
    if skills:
        runtime["skills"] = {"bindings": skills}
    knowledge = spec.get("knowledge")
    if knowledge:
        runtime["rag"] = deepcopy(knowledge.get("rag", {}))
    prompt = spec.get("legacy_system_prompt") or ""
    if spec.get("prompt_ref"):
        prompt = definitions[spec["prompt_ref"]]["spec"]["content"]
    output = deepcopy(spec.get("output") or {})
    if output.get("contract_ref"):
        contract = definitions[output["contract_ref"]]["spec"]
        output["output_schema"] = deepcopy(contract["output_schema"])
    if spec.get("behavior") is not None:
        prompt = assemble_system_instructions(
            metadata["name"],
            metadata.get("description", ""),
            canonicalize_behavior_spec(spec["behavior"]),
        )
    parameters = spec["model"].get("parameters", {})
    settings = {
        "runtime_config": runtime,
        "external_context_contract": inspection["external_context_contract"],
    }
    if output.get("response_format") is not None:
        settings["response_format"] = deepcopy(output["response_format"])
    if output.get("output_schema") is not None:
        settings["output_schema"] = deepcopy(output["output_schema"])
    if definitions[primary_key]["spec"].get("base_url"):
        settings["base_url"] = definitions[primary_key]["spec"]["base_url"]
    create = CreateAgentInput.model_validate(
        {
            "project_id": project_id,
            "name": metadata["name"],
            "description": metadata.get("description", ""),
            "type": spec.get("type", "chat"),
            "behavior_spec": spec.get("behavior"),
            "system_prompt": prompt,
            "provider_model_id": primary["id"],
            "provider": primary["provider"],
            "model": primary["model"],
            "provider_credential_id": primary["provider_credential_id"],
            "fallback_provider_model_id": fallback["id"] if fallback else None,
            "fallback_provider": fallback["provider"] if fallback else None,
            "fallback_model": fallback["model"] if fallback else None,
            "fallback_credential_id": fallback["provider_credential_id"]
            if fallback
            else None,
            "temperature": parameters.get("temperature"),
            "max_output_tokens": parameters.get("max_output_tokens"),
            "session_mode": spec.get("session", {}).get("mode", "stateless"),
            "status": "inactive",
            "settings": settings,
        }
    )
    prepared = Agent(**create.model_dump())
    _force_strict_json_settings(
        prepared, default_context_manager="stdcm", initialize_context_manager=True
    )
    create.settings = prepared.settings
    runtime = prepared.settings["runtime_config"]
    output["response_format"] = prepared.settings.get("response_format")
    if agent_id is None:
        return create.model_dump(mode="json")
    fields = create.model_dump(mode="json", exclude={"type", "status", "settings"})
    fields.update(
        {
            "agent_id": str(agent_id),
            "version": "auto",
            "agent_status": "active",
            "runtime_config": runtime,
            "response_format": output.get("response_format"),
            "output_schema": output.get("output_schema"),
            "external_context_contract": inspection["external_context_contract"],
            "base_url": settings.get("base_url"),
            "model_spec_snapshot": primary["spec"],
            "model_spec_hash": primary["spec_hash"],
            "fallback_model_spec_snapshot": fallback["spec"] if fallback else None,
            "fallback_model_spec_hash": fallback["spec_hash"] if fallback else None,
            "release_notes": release_notes,
        }
    )
    for portable_field, native_field in (("prompt_ref", "prompt_version_id"),):
        if spec.get(portable_field):
            fields[native_field] = resources["prompt:" + document["metadata"]["key"]][
                "id"
            ]
    if output.get("contract_ref"):
        fields["contract_version_id"] = resources[
            "contract:" + document["metadata"]["key"]
        ]["id"]
    if knowledge:
        fields["knowledge_version_id"] = resources[
            "knowledge-version:" + document["metadata"]["key"]
        ]["id"]
        fields["collection_ids"] = [
            resources[knowledge["source"]["ref"]]["collection_id"]
        ]
    return CreateReleaseInput.model_validate(fields).model_dump(mode="json")
