from __future__ import annotations

from typing import Protocol

from modules.agent.application.interfaces.release_activation_repository import (
    AgentReleaseActivationRepository,
)
from modules.agent.application.interfaces.repositories import (
    AgentReleaseRepository,
    ToolRepository,
)
from modules.agent.application.tool_release_snapshots import build_release_tool_runtime
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import (
    AutoCompatibleReleaseLifecycleUseCase,
)
from modules.agent.application.use_cases.release_lifecycle_use_cases import (
    AutoCreateReleaseUseCase,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import ReleaseNotFoundError
from modules.agent.domain.release_activation import AgentReleaseActivation
from shared.contracts.errors import ValidationError


class ReleaseKnowledgeValidator(Protocol):
    async def validate(self, release: AgentRelease) -> None: ...


def _tool_snapshots(runtime_config):
    if not isinstance(runtime_config, dict):
        return None
    tools = runtime_config.get("tools")
    if not isinstance(tools, dict):
        return None
    snapshots = tools.get("snapshots")
    return snapshots if isinstance(snapshots, list) else None


def _release_sort_key(release: AgentRelease) -> float:
    value = release.updated_at or release.created_at
    return value.timestamp() if value is not None else 0.0


def _audit_text(input_dto, field_name: str) -> str | None:
    value = getattr(input_dto, field_name, None) if input_dto is not None else None
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


class KnowledgeSafeCreateReleaseUseCase(AutoCreateReleaseUseCase):
    def __init__(
        self,
        release_repo: AgentReleaseRepository,
        knowledge_validator: ReleaseKnowledgeValidator,
        tool_repo: ToolRepository,
    ) -> None:
        super().__init__(release_repo)
        self._knowledge_validator = knowledge_validator
        self._tool_repo = tool_repo

    async def execute(self, input_dto, change_kind: str = "change"):
        candidate = AgentRelease(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            knowledge_version_id=input_dto.knowledge_version_id,
        )
        await self._knowledge_validator.validate(candidate)

        previous_snapshots = None
        drafts = await self._release_repo.list_by_status(
            input_dto.agent_id,
            ReleaseStatus.draft,
        )
        if drafts:
            current_draft = max(drafts, key=_release_sort_key)
            previous_snapshots = _tool_snapshots(current_draft.runtime_config)

        runtime_config = dict(input_dto.runtime_config or {})
        raw_tools = runtime_config.get("tools")
        if isinstance(raw_tools, dict):
            runtime_config["tools"] = await build_release_tool_runtime(
                self._tool_repo,
                project_id=input_dto.project_id,
                raw_tool_ids=raw_tools.get("tool_ids"),
                raw_permissions=raw_tools.get("permissions"),
                previous_snapshots=previous_snapshots,
            )
        input_dto.runtime_config = runtime_config or None

        return await super().execute(input_dto, change_kind=change_kind)


class KnowledgeSafeReleaseLifecycleUseCase(AutoCompatibleReleaseLifecycleUseCase):
    def __init__(
        self,
        release_repo: AgentReleaseRepository,
        knowledge_validator: ReleaseKnowledgeValidator,
        activation_repo: AgentReleaseActivationRepository | None = None,
        *,
        activation_action: str = "reactivate",
    ) -> None:
        super().__init__(release_repo)
        self._knowledge_validator = knowledge_validator
        self._activation_repo = activation_repo
        self._activation_action = activation_action

    async def execute(self, agent_id, release_id, input_dto=None, **kwargs):
        release = await self._release_repo.get_by_id(release_id)
        if release is None or release.agent_id != agent_id:
            raise ReleaseNotFoundError
        await self._knowledge_validator.validate(release)

        target_status = getattr(
            kwargs.get("target_status", "production"),
            "value",
            kwargs.get("target_status", "production"),
        )
        previous = None
        existing_release_ids: set = set()
        if target_status == ReleaseStatus.production.value:
            snapshot_kind = getattr(release, "snapshot_kind", None)
            if snapshot_kind == "staging":
                release_notes = _audit_text(input_dto, "release_notes")
                if release_notes is None or len(release_notes) < 3:
                    raise ValidationError(
                        "Agent Release description is required before publishing Production"
                    )
            elif snapshot_kind == "release":
                change_description = _audit_text(input_dto, "change_description")
                if change_description is None or len(change_description) < 3:
                    raise ValidationError(
                        "Agent Production activation reason is required"
                    )

            previous = await self._release_repo.get_active_production(agent_id)
            existing_release_ids = {
                item.id
                for item in await self._release_repo.list_by_agent(agent_id)
                if getattr(item, "snapshot_kind", None) == "release"
            }

        result = await super().execute(agent_id, release_id, input_dto, **kwargs)

        if (
            target_status == ReleaseStatus.production.value
            and self._activation_repo is not None
            and (previous is None or previous.id != result.id)
        ):
            action = self._activation_action
            if action != "rollback":
                action = (
                    "reactivate" if result.id in existing_release_ids else "deploy"
                )
            change_description = _audit_text(input_dto, "change_description")
            if change_description is None and action == "deploy":
                change_description = _audit_text(input_dto, "release_notes")
            await self._activation_repo.save(
                AgentReleaseActivation(
                    project_id=result.project_id,
                    agent_id=result.agent_id,
                    release_id=result.id,
                    previous_release_id=(previous.id if previous is not None else None),
                    action=action,
                    change_description=change_description,
                    created_by=getattr(input_dto, "user_id", None),
                )
            )

        return result


class KnowledgeSafeRollbackReleaseUseCase(KnowledgeSafeReleaseLifecycleUseCase):
    pass
