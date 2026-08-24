from __future__ import annotations

from uuid import uuid4

from modules.agent.domain.entities import Agent
from modules.agent.domain.enums import Provider, SessionMode
from modules.agent.infra.execution.frozen_snapshot_runtime import (
    FrozenSnapshotStructuredOutputRuntime,
)


def test_frozen_snapshot_replaces_mutable_draft_runtime_state_exactly() -> None:
    current_provider_model_id = uuid4()
    current_credential_id = uuid4()
    current_fallback_model_id = uuid4()
    current_fallback_credential_id = uuid4()
    frozen_provider_model_id = uuid4()
    frozen_credential_id = uuid4()
    frozen_knowledge_version_id = uuid4()

    agent = Agent(
        project_id=uuid4(),
        provider_model_id=current_provider_model_id,
        provider_credential_id=current_credential_id,
        fallback_provider_model_id=current_fallback_model_id,
        fallback_credential_id=current_fallback_credential_id,
        provider=Provider.anthropic,
        model="current-model",
        fallback_provider=Provider.openai,
        fallback_model="current-fallback",
        system_prompt="current prompt",
        temperature=0.9,
        max_output_tokens=900,
        session_mode=SessionMode.stateless,
        settings={
            "knowledge_version_id": str(uuid4()),
            "response_format": {"enabled": False},
            "runtime_config": {
                "rag": {"top_k": 99},
                "tools": {"tool_ids": [str(uuid4())]},
            },
        },
    )
    snapshot = {
        "system_prompt": "frozen prompt",
        "provider_model_id": str(frozen_provider_model_id),
        "provider_credential_id": str(frozen_credential_id),
        "provider": "openai",
        "model": "frozen-model",
        "fallback_provider_model_id": None,
        "fallback_credential_id": None,
        "fallback_provider": None,
        "fallback_model": None,
        "temperature": None,
        "max_output_tokens": 321,
        "session_mode": "stateful",
        "knowledge_version_id": str(frozen_knowledge_version_id),
        "response_format": {
            "enabled": True,
            "type": "json",
            "schema": {"type": "object"},
        },
        "runtime_config": {
            "rag": {"top_k": 4, "candidate_k": 8},
            "tools": {"tool_ids": []},
        },
    }

    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )
    resolved = runtime._apply_snapshot_override(agent, snapshot)

    assert resolved is agent
    assert agent.system_prompt == "frozen prompt"
    assert agent.provider_model_id == frozen_provider_model_id
    assert agent.provider_credential_id == frozen_credential_id
    assert agent.provider == Provider.openai
    assert agent.model == "frozen-model"
    assert agent.fallback_provider_model_id is None
    assert agent.fallback_credential_id is None
    assert agent.fallback_provider is None
    assert agent.fallback_model is None
    assert agent.temperature is None
    assert agent.max_output_tokens == 321
    assert agent.session_mode == SessionMode.stateful
    assert agent.settings == {
        "knowledge_version_id": str(frozen_knowledge_version_id),
        "response_format": {
            "enabled": True,
            "type": "json",
            "schema": {"type": "object"},
        },
        "runtime_config": {
            "rag": {"top_k": 4, "candidate_k": 8},
            "tools": {"tool_ids": []},
        },
    }
