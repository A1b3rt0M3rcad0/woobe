from __future__ import annotations

from modules.agent.application.tool_release_snapshots import build_release_tool_runtime
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import AutoCompatibleReleaseLifecycleUseCase
from modules.agent.application.use_cases.release_lifecycle_use_cases import AutoCreateReleaseUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import ReleaseNotFoundError


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


class KnowledgeSafeCreateReleaseUseCase(AutoCreateReleaseUseCase):
    def __init__(self, release_repo, knowledge_validator, tool_repo) -> None:
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
    def __init__(self, release_repo, knowledge_validator) -> None:
        super().__init__(release_repo)
        self._knowledge_validator = knowledge_validator

    async def execute(self, agent_id, release_id, input_dto=None, **kwargs):
        release = await self._release_repo.get_by_id(release_id)
        if release is None or release.agent_id != agent_id:
            raise ReleaseNotFoundError
        await self._knowledge_validator.validate(release)
        return await super().execute(agent_id, release_id, input_dto, **kwargs)


class KnowledgeSafeRollbackReleaseUseCase(KnowledgeSafeReleaseLifecycleUseCase):
    pass
