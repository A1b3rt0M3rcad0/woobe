from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from copy import deepcopy
from enum import Enum
from typing import Any
from uuid import UUID

from modules.agent.application.interfaces.context_policy import canonicalize_context_runtime_config
from modules.agent.application.tool_templates import collect_project_environment_keys
from modules.agent.domain.enums import CredentialStatus, ProviderModelStatus, ToolStatus
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from shared.contracts.errors import ValidationError
from shared.project_environment import PreparedProjectEnvironmentValue

_SECRET_PATTERN = re.compile(r"\{\{secret:([^}]+)\}\}")

ToolFromSnapshot = Callable[[dict[str, Any]], Any]
ToolWithPermissions = Callable[[Any, Any], Any]
ToolToSnapshot = Callable[[Any], dict[str, Any]]
SkillBindingFreezer = Callable[..., Awaitable[dict[str, Any]]]
_skill_binding_freezer: SkillBindingFreezer | None = None


def configure_skill_binding_freezer(freezer: SkillBindingFreezer) -> None:
    """Bind the Skill application service from the composition root."""
    global _skill_binding_freezer
    _skill_binding_freezer = freezer


def _value(value: object) -> object:
    return getattr(value, "value", value)


def json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def collect_secret_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, str):
        names.update(
            match.group(1).strip()
            for match in _SECRET_PATTERN.finditer(value)
            if match.group(1).strip()
        )
    elif isinstance(value, dict):
        for item in value.values():
            names.update(collect_secret_names(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            names.update(collect_secret_names(item))
    return names


def _runtime_tools_config(agent: Any) -> dict[str, Any]:
    runtime = (agent.settings or {}).get("runtime_config")
    if not isinstance(runtime, dict):
        return {}
    tools = runtime.get("tools")
    return tools if isinstance(tools, dict) else {}


async def prepare_tool_state(
    repositories: AgentRuntimeRepositories,
    *,
    agent: Any,
    tool_from_snapshot: ToolFromSnapshot,
    tool_with_permissions: ToolWithPermissions,
) -> tuple[list[Any], dict[str, str]]:
    """Resolve the exact Tool set and encrypted secrets inside Acceptance."""

    tools_config = _runtime_tools_config(agent)
    raw_ids = tools_config.get("tool_ids")
    raw_snapshots = tools_config.get("snapshots")
    raw_permissions = tools_config.get("permissions")
    permission_map = raw_permissions if isinstance(raw_permissions, dict) else {}

    snapshot_index: dict[str, dict[str, Any]] = {}
    if isinstance(raw_snapshots, list):
        snapshot_index = {
            str(item.get("id")): item
            for item in raw_snapshots
            if isinstance(item, dict) and item.get("id") is not None
        }

    selected_ids: list[UUID] = []
    if isinstance(raw_ids, list):
        for raw_id in raw_ids:
            try:
                selected_ids.append(
                    raw_id if isinstance(raw_id, UUID) else UUID(str(raw_id))
                )
            except (TypeError, ValueError) as exc:
                raise ValidationError("Agent runtime contains an invalid Tool id") from exc
    elif snapshot_index:
        selected_ids = [UUID(value) for value in snapshot_index]

    tools: list[Any] = []
    if selected_ids:
        for tool_id in selected_ids:
            snapshot = snapshot_index.get(str(tool_id))
            if snapshot is not None:
                tool = tool_from_snapshot(snapshot)
            else:
                tool = await repositories.tools.get_by_id(tool_id)
            if tool is None or tool.project_id != agent.project_id:
                raise ValidationError("Selected Tool was not found in this Project")
            if _value(tool.status) != ToolStatus.ACTIVE.value:
                raise ValidationError(f"Selected Tool is not active: {tool.name}")
            tools.append(
                tool_with_permissions(
                    tool,
                    permission_map.get(str(tool_id)),
                )
            )
    else:
        tools = list(await repositories.tools.list_by_agent(agent.id, status="active"))

    secret_names: set[str] = set()
    for tool in tools:
        secret_names.update(collect_secret_names(tool.config or {}))

    encrypted_by_name: dict[str, str] = {}
    for name in sorted(secret_names):
        try:
            secret = await repositories.tool_secrets.get_by_name(agent.project_id, name)
        except Exception as exc:
            raise ValidationError(f"Configured Tool secret was not found: {name}") from exc
        encrypted_by_name[name] = secret.encrypted_value
    return tools, encrypted_by_name


async def prepare_project_environment_state(
    repositories: AgentRuntimeRepositories,
    *,
    project_id: UUID,
    environment: str,
    tools: list[Any],
) -> dict[str, PreparedProjectEnvironmentValue]:
    """Read only Project Environment keys referenced by the accepted Tool set.

    Missing values are intentionally not rejected here. A Tool may never be invoked
    during the Run; resolution fails explicitly only if that Tool actually requires
    an unavailable key.
    """

    keys: set[str] = set()
    for tool in tools:
        keys.update(collect_project_environment_keys(tool.config or {}))
    if not keys:
        return {}

    reader = repositories.project_environment
    if reader is None:
        raise ValidationError("Project Environment runtime reader is unavailable")
    return await reader.read_values(
        project_id=project_id,
        environment=environment,
        keys=keys,
    )


async def prepare_rag_binding(
    repositories: AgentRuntimeRepositories,
    *,
    agent: Any,
) -> dict[str, Any] | None:
    settings = dict(agent.settings or {})
    knowledge_version_id = settings.get("knowledge_version_id")
    if not knowledge_version_id:
        return None

    try:
        knowledge_id = (
            knowledge_version_id
            if isinstance(knowledge_version_id, UUID)
            else UUID(str(knowledge_version_id))
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid knowledge_version_id") from exc

    knowledge = await repositories.knowledge_versions.get_by_id(knowledge_id)
    if knowledge is None:
        raise ValidationError("Configured KnowledgeVersion was not found")
    if knowledge.project_id != agent.project_id or knowledge.agent_id != agent.id:
        raise ValidationError("Configured KnowledgeVersion does not belong to this Agent")

    metadata = dict(knowledge.snapshot_metadata or {})
    vector_snapshot_id = metadata.get("vector_snapshot_id")
    if not vector_snapshot_id:
        raise ValidationError("Configured KnowledgeVersion has no vector snapshot")
    try:
        snapshot_id = (
            vector_snapshot_id
            if isinstance(vector_snapshot_id, UUID)
            else UUID(str(vector_snapshot_id))
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("Invalid vector_snapshot_id") from exc

    snapshot = await repositories.vector_snapshots.get_by_id(snapshot_id)
    if snapshot is None or snapshot.project_id != agent.project_id:
        raise ValidationError("Configured vector snapshot was not found")
    if snapshot.status != VECTOR_SNAPSHOT_READY:
        raise ValidationError("Configured vector snapshot is not READY")
    if not snapshot.snapshot_hash:
        raise ValidationError("Configured vector snapshot has no immutable hash")

    provider_model = await repositories.provider_models.get_by_id(
        snapshot.embedding_provider_model_id
    )
    if provider_model is None or provider_model.project_id != agent.project_id:
        raise ValidationError("Embedding provider model was not found")
    if _value(provider_model.status) != ProviderModelStatus.active.value:
        raise ValidationError("Embedding provider model must be active")
    capability = str((provider_model.metadata or {}).get("capability") or "").lower()
    if capability not in {"embedding", "embeddings"} and "embed" not in provider_model.model.lower():
        raise ValidationError("Configured provider model is not an embedding model")

    credential = await repositories.provider_credentials.get_by_id(
        provider_model.provider_credential_id
    )
    if credential is None or credential.project_id != agent.project_id:
        raise ValidationError("Embedding provider credential was not found")
    if _value(credential.status) != CredentialStatus.active.value:
        raise ValidationError("Embedding provider credential must be active")

    snapshot_documents = await repositories.vector_snapshots.list_snapshot_documents(
        snapshot.id
    )
    return {
        "knowledge": knowledge,
        "snapshot": snapshot,
        "provider_model": provider_model,
        "credential": credential,
        "snapshot_documents": snapshot_documents,
    }


def build_execution_snapshot(
    *,
    agent: Any,
    tools: list[Any],
    rag_binding: dict[str, Any] | None,
    release_id: UUID | None,
    release_version: str | None,
    tool_to_snapshot: ToolToSnapshot,
) -> dict[str, Any]:
    settings = deepcopy(agent.settings or {})
    settings["runtime_config"] = canonicalize_context_runtime_config(
        settings.get("runtime_config")
    )
    snapshot: dict[str, Any] = {
        "agent": {
            "id": str(agent.id),
            "name": getattr(agent, "name", None),
            "description": getattr(agent, "description", None),
            "behavior_spec": deepcopy(getattr(agent, "behavior_spec", None)),
            "system_prompt": agent.system_prompt,
            "provider_model_id": str(agent.provider_model_id) if getattr(agent, "provider_model_id", None) else None,
            "provider_credential_id": str(agent.provider_credential_id) if getattr(agent, "provider_credential_id", None) else None,
            "provider": str(_value(agent.provider)),
            "model": agent.model,
            "fallback_provider_model_id": str(agent.fallback_provider_model_id) if getattr(agent, "fallback_provider_model_id", None) else None,
            "fallback_credential_id": str(agent.fallback_credential_id) if getattr(agent, "fallback_credential_id", None) else None,
            "fallback_provider": str(_value(agent.fallback_provider)) if getattr(agent, "fallback_provider", None) else None,
            "fallback_model": getattr(agent, "fallback_model", None),
            "temperature": agent.temperature,
            "max_output_tokens": agent.max_output_tokens,
            "session_mode": str(_value(agent.session_mode)),
            "settings": settings,
        },
        "release": {
            "id": str(release_id) if release_id else None,
            "version": release_version,
        },
        "tools": [tool_to_snapshot(tool) for tool in tools],
    }
    if rag_binding:
        knowledge = rag_binding["knowledge"]
        vector_snapshot = rag_binding["snapshot"]
        snapshot["knowledge"] = {
            "knowledge_version_id": str(knowledge.id),
            "knowledge_version": knowledge.version,
            "vector_snapshot_id": str(vector_snapshot.id),
            "vector_snapshot_version": vector_snapshot.version,
            "vector_snapshot_hash": vector_snapshot.snapshot_hash,
            "embedding_provider_model_id": str(vector_snapshot.embedding_provider_model_id),
            "embedding_provider": vector_snapshot.embedding_provider,
            "embedding_model": vector_snapshot.embedding_model,
            "embedding_dimensions": vector_snapshot.embedding_dimensions,
        }
    return json_safe(snapshot)


async def prepare_skill_state(repositories: AgentRuntimeRepositories, *, agent: Any) -> None:
    settings = deepcopy(agent.settings or {})
    runtime = settings.get("runtime_config")
    if isinstance(runtime, dict) and "skills" in runtime:
        if _skill_binding_freezer is None:
            raise RuntimeError("Skill binding freezer was not configured")
        settings["runtime_config"] = await _skill_binding_freezer(
            repositories.skills,
            project_id=agent.project_id,
            runtime_config=runtime,
        )
        agent.settings = settings
