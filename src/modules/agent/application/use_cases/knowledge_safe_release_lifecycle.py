from __future__ import annotations

from modules.agent.application.tool_release_snapshots import build_release_tool_runtime
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import AutoCompatibleReleaseLifecycleUseCase
from modules.agent.application.use_cases.release_lifecycle_use_cases import AutoCreateReleaseUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.errors import ReleaseNotFoundError


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

        runtime_config = dict(input_dto.runtime_config or {})
        raw_tools = runtime_config.get("tools")
        if isinstance(raw_tools, dict):
            runtime_config["tools"] = await build_release_tool_runtime(
                self._tool_repo,
                project_id=input_dto.project_id,
                raw_tool_ids=raw_tools.get("tool_ids"),
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
