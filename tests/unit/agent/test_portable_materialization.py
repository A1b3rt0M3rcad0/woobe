from uuid import uuid4

from modules.agent.application.portable_materialization import (
    compile_imported_agent_inputs,
)
from modules.agent.application.use_cases.ai_provider_model_cases import (
    CreateProviderModelUseCase,
)
from modules.agent.application.dtos.ai_dtos import CreateProviderModelInput
from modules.agent.domain.entities import ProviderCredential
from modules.agent.domain.enums import Provider


def model(project, provider="openai_compatible"):
    credential = ProviderCredential(project_id=project, provider=Provider(provider))
    item = CreateProviderModelUseCase.prepare_definition(
        CreateProviderModelInput(
            project_id=project,
            provider_credential_id=credential.id,
            name="Language",
            model="fake",
        ),
        credential,
    )
    return {
        "id": str(item.id),
        "provider": provider,
        "model": item.model,
        "provider_credential_id": str(credential.id),
        "spec": item.spec,
        "spec_hash": item.spec_hash,
    }


def test_owner_compiles_primary_fallback_prompt_contract_and_complete_inactive_preparation():
    project = uuid4()
    definition = {
        "kind": "Agent",
        "metadata": {"key": "assistant", "name": "Assistant", "description": "Support"},
        "spec": {
            "prompt_ref": "prompt",
            "model": {
                "primary": {"ref": "primary"},
                "fallback": {"ref": "fallback"},
                "parameters": {"temperature": 0.2, "max_output_tokens": 128},
            },
            "session": {"mode": "stateful"},
            "output": {
                "contract_ref": "contract",
                "response_format": {
                    "type": "json",
                    "enabled": True,
                    "schema": {"type": "object"},
                    "strict": False,
                },
            },
        },
    }
    definitions = {
        "primary": {"spec": {"base_url": "https://provider.test/v1"}},
        "fallback": {"spec": {}},
        "prompt": {"spec": {"content": "Help carefully"}},
        "contract": {"spec": {"output_schema": {"type": "object"}}},
    }
    resources = {
        "primary": model(project),
        "fallback": model(project),
        "prompt:assistant": {"id": str(uuid4())},
        "contract:assistant": {"id": str(uuid4())},
    }
    prepared = compile_imported_agent_inputs(
        project_id=project,
        document=definition,
        definitions=definitions,
        resources=resources,
    )
    assert prepared["status"] == "inactive"
    assert prepared["settings"]["response_format"]["strict"] is True
    draft = compile_imported_agent_inputs(
        project_id=project,
        document=definition,
        definitions=definitions,
        resources=resources,
        agent_id=uuid4(),
    )
    assert draft["system_prompt"] == "Help carefully"
    assert draft["prompt_version_id"] == resources["prompt:assistant"]["id"]
    assert draft["contract_version_id"] == resources["contract:assistant"]["id"]
    assert draft["model_spec_snapshot"] == resources["primary"]["spec"]
    assert draft["fallback_model_spec_snapshot"] == resources["fallback"]["spec"]
    assert draft["base_url"] == "https://provider.test/v1"
    assert draft["temperature"] == 0.2 and draft["session_mode"] == "stateful"
    assert draft["response_format"] == prepared["settings"]["response_format"]


def test_behavior_uses_native_instruction_assembly_for_preparation_and_draft():
    from modules.agent.application.system_instruction_assembler import (
        assemble_system_instructions,
    )

    project = uuid4()
    behavior = {"schema_version": 1, "objective": "Support customers"}
    definition = {
        "kind": "Agent",
        "metadata": {"key": "assistant", "name": "Assistant", "description": "Support"},
        "spec": {"behavior": behavior, "model": {"primary": {"ref": "primary"}}},
    }
    resources = {"primary": model(project)}
    definitions = {"primary": {"spec": {}}}
    prepared = compile_imported_agent_inputs(
        project_id=project,
        document=definition,
        definitions=definitions,
        resources=resources,
    )
    draft = compile_imported_agent_inputs(
        project_id=project,
        document=definition,
        definitions=definitions,
        resources=resources,
        agent_id=uuid4(),
    )
    expected = assemble_system_instructions(
        "Assistant", "Support", prepared["behavior_spec"]
    )
    assert prepared["system_prompt"] == draft["system_prompt"] == expected
