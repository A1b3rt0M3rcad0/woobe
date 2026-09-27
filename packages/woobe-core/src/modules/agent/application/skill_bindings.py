from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from modules.agent.application.interfaces.context_assembler import (
    context_assembler_key_from_runtime_config,
)
from modules.agent.application.interfaces.context_policy import resolve_context_policy
from modules.agent.application.interfaces.skill_repository import SkillRepository
from modules.agent.domain.skills import skill_package_hash
from shared.contracts.errors import ValidationError


class AgentSkillBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_id: UUID
    skill_version_id: UUID
    enabled: bool = True


class AgentSkillsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bindings: list[AgentSkillBinding] = Field(default_factory=list, max_length=1000)
    snapshots: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)


def skill_bindings(runtime_config: object) -> AgentSkillsConfig:
    runtime = runtime_config if isinstance(runtime_config, dict) else {}
    return AgentSkillsConfig.model_validate(runtime.get("skills") or {})


def validate_skill_context(
    runtime_config: dict, bindings: list[AgentSkillBinding]
) -> None:
    if not any(item.enabled for item in bindings):
        return
    manager = context_assembler_key_from_runtime_config(runtime_config)
    if str(manager) != "stdcm":
        raise ValidationError("Enabled Skills require Standard Context Manager")
    policy = resolve_context_policy(runtime_config)
    if "TOOL" not in policy.allowed_sources:
        raise ValidationError("Context Policy must allow TOOL receipts for Skills")
    if "SKILL" not in policy.allowed_sources:
        raise ValidationError("Context Policy must allow the SKILL source")
    if policy.skills is None:
        raise ValidationError(
            "Configure the Skills context budget before enabling Skills"
        )


async def freeze_skill_bindings(
    repository: SkillRepository | None,
    *,
    project_id: UUID,
    runtime_config: object,
) -> dict[str, Any]:
    """Resolve only explicit version ids; never trust client-supplied package bytes."""
    result = deepcopy(runtime_config) if isinstance(runtime_config, dict) else {}
    if "skills" not in result:
        return result
    config = skill_bindings(result)
    validate_skill_context(result, config.bindings)
    seen: set[UUID] = set()
    snapshots = []
    total_bytes = 0
    for binding in config.bindings:
        if binding.skill_id in seen:
            raise ValidationError(
                "Only one version of each Skill can be installed on an Agent"
            )
        seen.add(binding.skill_id)
        if repository is None:
            raise ValidationError("Skill catalog is unavailable")
        version = await repository.get_version(project_id, binding.skill_version_id)
        if version is None or version.skill_id != binding.skill_id:
            raise ValidationError(
                "Installed Skill version was not found in this Project"
            )
        if skill_package_hash(version.package) != version.package_hash:
            raise ValidationError("Stored Skill package failed its integrity check")
        total_bytes += len(
            json.dumps(version.package, ensure_ascii=False).encode("utf-8")
        )
        if total_bytes > 4_000_000:
            raise ValidationError(
                "Installed Skill packages exceed the 4 MB Agent snapshot limit"
            )
        snapshots.append(version.snapshot())
    result["skills"] = {
        "bindings": [item.model_dump(mode="json") for item in config.bindings],
        "snapshots": snapshots,
    }
    return result


def frozen_enabled_skills(
    runtime_config: object, project_id: UUID
) -> list[dict[str, Any]]:
    runtime = runtime_config if isinstance(runtime_config, dict) else {}
    config = skill_bindings(runtime)
    validate_skill_context(runtime, config.bindings)
    versions = {item.get("skill_version_id"): item for item in config.snapshots}
    enabled = []
    for binding in config.bindings:
        if not binding.enabled:
            continue
        snapshot = versions.get(str(binding.skill_version_id))
        if (
            snapshot is None
            or snapshot.get("project_id") != str(project_id)
            or snapshot.get("skill_id") != str(binding.skill_id)
            or not isinstance(snapshot.get("package"), dict)
            or skill_package_hash(snapshot["package"]) != snapshot.get("package_hash")
        ):
            raise ValidationError("Run contains an invalid frozen Skill binding")
        enabled.append(deepcopy(snapshot))
    return enabled
