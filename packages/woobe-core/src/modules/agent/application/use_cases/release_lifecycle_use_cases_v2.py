from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from modules.agent.application.context_assembler_registry import (
    canonicalize_context_assembler_runtime_config,
)
from modules.agent.application.context_policy import canonicalize_context_runtime_config
from modules.agent.application.execution_runtime_config import (
    canonicalize_execution_runtime_config,
)
from modules.agent.application.execution_strategy_config import (
    execution_strategy_from_runtime_config,
)
from modules.agent.application.dtos.ai_dtos import CreateReleaseInput, CreateReleaseOutput
from modules.agent.application.dtos.behavior_dtos import canonicalize_behavior_spec
from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.repositories import AgentReleaseRepository
from modules.agent.application.system_instruction_assembler import assemble_system_instructions
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import ReleaseNotFoundError
from modules.agent.domain.external_context_contract import (
    ExternalContextContractError,
    normalize_external_context_contract,
)
from modules.agent.domain.release_versioning import calculate_next_release_version
from shared.contracts.errors import ConflictError, ValidationError


_SINGLETON_STATUSES = {ReleaseStatus.draft, ReleaseStatus.staging, ReleaseStatus.production}
_SNAPSHOT_FIELDS = (
    "project_id", "agent_id", "prompt_version_id", "contract_version_id",
    "knowledge_version_id", "model_config_version_id", "provider_model_id",
    "fallback_provider_model_id", "name", "description", "behavior_spec", "system_prompt",
    "response_format", "output_schema", "external_context_contract", "provider", "model",
    "provider_credential_id", "fallback_provider", "fallback_model",
    "fallback_credential_id", "base_url", "temperature", "max_output_tokens",
    "session_mode", "agent_status", "collection_ids", "runtime_config",
    "risk_score", "created_by",
)


def _canonical_runtime_config(value) -> dict:
    runtime_config = canonicalize_context_assembler_runtime_config(value)
    # Validate an explicit strategy, but do not backfill historical snapshots that
    # predate this field. Absence is permanently defined as Standard, so preserving
    # it avoids changing old snapshot material/hashes while keeping behavior stable.
    strategy = execution_strategy_from_runtime_config(runtime_config)
    if "execution_strategy" in runtime_config:
        runtime_config["execution_strategy"] = strategy
    runtime_config = canonicalize_execution_runtime_config(runtime_config)
    runtime_config = canonicalize_context_runtime_config(runtime_config)
    raw_rag = runtime_config.get("rag")
    runtime_config["rag"] = RAGRuntimeConfig.model_validate(
        raw_rag if isinstance(raw_rag, dict) else {}
    ).model_dump()
    return runtime_config


def _canonical_external_context_contract(value):
    if value is None:
        return None
    try:
        return normalize_external_context_contract(value)
    except ExternalContextContractError as exc:
        raise ValidationError(str(exc)) from exc


def _release_to_output(saved: AgentRelease) -> CreateReleaseOutput:
    return CreateReleaseOutput(
        id=saved.id,
        project_id=saved.project_id,
        agent_id=saved.agent_id,
        version=saved.version,
        status=saved.status,
        snapshot_kind=getattr(saved, "snapshot_kind", None),
        prompt_version_id=saved.prompt_version_id,
        contract_version_id=saved.contract_version_id,
        knowledge_version_id=saved.knowledge_version_id,
        model_config_version_id=saved.model_config_version_id,
        provider_model_id=getattr(saved, "provider_model_id", None),
        fallback_provider_model_id=getattr(saved, "fallback_provider_model_id", None),
        name=saved.name,
        description=saved.description,
        behavior_spec=getattr(saved, "behavior_spec", None),
        system_prompt=saved.system_prompt,
        response_format=saved.response_format,
        output_schema=saved.output_schema,
        external_context_contract=saved.external_context_contract,
        provider=saved.provider,
        model=saved.model,
        provider_credential_id=saved.provider_credential_id,
        fallback_provider=saved.fallback_provider,
        fallback_model=saved.fallback_model,
        fallback_credential_id=saved.fallback_credential_id,
        base_url=saved.base_url,
        temperature=saved.temperature,
        max_output_tokens=saved.max_output_tokens,
        session_mode=saved.session_mode,
        agent_status=saved.agent_status,
        collection_ids=saved.collection_ids,
        runtime_config=saved.runtime_config,
        release_notes=saved.release_notes,
        risk_score=saved.risk_score,
        created_by=saved.created_by,
        promoted_by=saved.promoted_by,
        promoted_at=saved.promoted_at,
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


class AutoCreateReleaseUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(self, input_dto: CreateReleaseInput, change_kind: str = "change"):
        draft = await self._get_singleton(input_dto.agent_id, ReleaseStatus.draft)
        if draft is None:
            draft = AgentRelease(
                project_id=input_dto.project_id,
                agent_id=input_dto.agent_id,
                version="draft",
                status=ReleaseStatus.draft,
            )
        self._copy_input_to_release(input_dto, draft)
        draft.version = "draft"
        draft.status = ReleaseStatus.draft
        draft.snapshot_kind = "draft"
        return _release_to_output(await self._release_repo.save(draft))

    async def _get_singleton(self, agent_id: UUID, status: ReleaseStatus) -> AgentRelease | None:
        items = await self._release_repo.list_by_status(agent_id, status)
        if not items:
            return None
        primary = sorted(
            items,
            key=lambda item: item.updated_at or item.created_at or datetime.min,
            reverse=True,
        )[0]
        for stale in items:
            if stale.id != primary.id:
                stale.status = ReleaseStatus.archived
                await self._release_repo.save(stale)
        return primary

    def _copy_input_to_release(self, input_dto: CreateReleaseInput, release: AgentRelease) -> None:
        for field_name in _SNAPSHOT_FIELDS:
            value = getattr(input_dto, field_name)
            if field_name == "behavior_spec" and value is not None:
                value = canonicalize_behavior_spec(value)
            elif field_name == "runtime_config":
                value = _canonical_runtime_config(value)
            elif field_name == "external_context_contract":
                value = _canonical_external_context_contract(value)
            else:
                value = deepcopy(value)
            setattr(release, field_name, value)
        if release.behavior_spec is not None:
            release.system_prompt = assemble_system_instructions(
                release.name, release.description, release.behavior_spec
            )
        release.release_notes = getattr(input_dto, "release_notes", None)


class ReleaseLifecycleUseCase:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def execute(
        self,
        agent_id: UUID,
        release_id: UUID,
        input_dto=None,
        *,
        target_status: str = "production",
        user_id: UUID | None = None,
        copy_snapshot: bool = False,
        change_kind: str = "change",
    ):
        release_notes = getattr(input_dto, "release_notes", None) if input_dto is not None else None
        if input_dto is not None and user_id is None:
            user_id = getattr(input_dto, "user_id", None)
        release = await self._release_repo.get_by_id(release_id)
        if not release or release.agent_id != agent_id:
            raise ReleaseNotFoundError

        target = ReleaseStatus(target_status)
        if target not in _SINGLETON_STATUSES:
            raise ValueError("invalid release lifecycle target")
        if target == ReleaseStatus.draft:
            raise ConflictError("Draft is changed through Save Draft, not promotion")
        if target == ReleaseStatus.staging:
            if release.status != ReleaseStatus.draft or getattr(release, "snapshot_kind", "draft") != "draft":
                raise ConflictError("Staging can only be created from the current Agent Draft")
            saved = await self._copy_to_staging_snapshot(release, user_id=user_id)
            return _release_to_output(saved)

        snapshot_kind = getattr(release, "snapshot_kind", None)
        if release.status == ReleaseStatus.draft or snapshot_kind == "draft":
            raise ConflictError("Draft must be promoted to Staging before Production")
        if snapshot_kind == "release":
            saved = await self._activate_existing_release(release, user_id=user_id)
        elif snapshot_kind == "staging":
            saved = await self._copy_to_production_release(
                release,
                user_id=user_id,
                change_kind=change_kind,
                release_notes=release_notes,
            )
        else:
            raise ConflictError("Only an Agent Staging or Agent Release can be activated in Production")
        return _release_to_output(saved)

    async def _copy_to_staging_snapshot(self, source: AgentRelease, *, user_id: UUID | None) -> AgentRelease:
        await self._archive_current(source.agent_id, ReleaseStatus.staging)
        staged = self._new_snapshot_copy(
            source,
            version=await self._next_staging_version(source.agent_id),
            status=ReleaseStatus.staging,
            release_notes=source.release_notes,
            promoted_by=user_id,
            snapshot_kind="staging",
        )
        return await self._release_repo.save(staged)

    async def _activate_existing_release(self, release: AgentRelease, *, user_id: UUID | None) -> AgentRelease:
        if getattr(release, "snapshot_kind", None) != "release":
            raise ConflictError("Only an immutable Agent Release can be activated in Production")
        if release.status == ReleaseStatus.production:
            return release
        await self._archive_current(
            release.agent_id,
            ReleaseStatus.production,
            exclude_id=release.id,
        )
        release.status = ReleaseStatus.production
        release.promoted_by = user_id
        release.promoted_at = datetime.now(timezone.utc)
        return await self._release_repo.save(release)

    async def _move_to_status(self, release: AgentRelease, target: ReleaseStatus, *, user_id: UUID | None) -> AgentRelease:
        await self._archive_current(release.agent_id, target, exclude_id=release.id)
        release.status = target
        if target == ReleaseStatus.production:
            release.snapshot_kind = "release"
            release.promoted_by = user_id
            release.promoted_at = datetime.now(timezone.utc)
        return await self._release_repo.save(release)

    async def _copy_to_production_release(
        self,
        release: AgentRelease,
        *,
        user_id: UUID | None,
        change_kind: str,
        release_notes: str | None = None,
    ) -> AgentRelease:
        await self._archive_current(release.agent_id, ReleaseStatus.production)
        cloned = self._new_snapshot_copy(
            release,
            version=await self._next_version(release.agent_id, change_kind),
            status=ReleaseStatus.production,
            release_notes=release_notes,
            promoted_by=user_id,
            snapshot_kind="release",
        )
        return await self._release_repo.save(cloned)

    async def _archive_current(
        self,
        agent_id: UUID,
        status: ReleaseStatus,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        for release in await self._release_repo.list_by_status(agent_id, status):
            if exclude_id is not None and release.id == exclude_id:
                continue
            release.status = (
                ReleaseStatus.released
                if status == ReleaseStatus.production
                else ReleaseStatus.archived
            )
            await self._release_repo.save(release)

    async def _get_singleton(self, agent_id: UUID, status: ReleaseStatus) -> AgentRelease | None:
        items = await self._release_repo.list_by_status(agent_id, status)
        if not items:
            return None
        primary = sorted(
            items,
            key=lambda item: item.updated_at or item.created_at or datetime.min,
            reverse=True,
        )[0]
        for stale in items:
            if stale.id != primary.id:
                stale.status = (
                    ReleaseStatus.released
                    if status == ReleaseStatus.production
                    else ReleaseStatus.archived
                )
                await self._release_repo.save(stale)
        return primary

    async def _next_staging_version(self, agent_id: UUID) -> str:
        releases = await self._release_repo.list_by_agent(agent_id)
        used = {item.version for item in releases}
        number = 1 + sum(
            1 for item in releases if getattr(item, "snapshot_kind", None) == "staging"
        )
        while f"staging-r{number}" in used:
            number += 1
        return f"staging-r{number}"

    async def _next_version(self, agent_id: UUID, change_kind: str) -> str:
        releases = await self._release_repo.list_by_agent(agent_id)
        historical_versions = [
            item.version
            for item in releases
            if getattr(item, "snapshot_kind", None) == "release"
        ]
        return calculate_next_release_version(historical_versions, change_kind)

    def _copy_snapshot(self, source: AgentRelease, target: AgentRelease) -> None:
        for field_name in _SNAPSHOT_FIELDS:
            value = getattr(source, field_name)
            if field_name == "runtime_config":
                value = _canonical_runtime_config(value)
            elif field_name == "external_context_contract":
                value = _canonical_external_context_contract(value)
            else:
                value = deepcopy(value)
            setattr(target, field_name, value)

    def _new_snapshot_copy(
        self,
        source: AgentRelease,
        *,
        version: str,
        status: ReleaseStatus,
        release_notes: str | None,
        promoted_by: UUID | None,
        snapshot_kind: str,
    ) -> AgentRelease:
        cloned = AgentRelease()
        self._copy_snapshot(source, cloned)
        cloned.version = version
        cloned.status = status
        cloned.snapshot_kind = snapshot_kind
        cloned.release_notes = release_notes
        cloned.promoted_by = promoted_by
        cloned.promoted_at = datetime.now(timezone.utc)
        cloned.created_at = None
        cloned.updated_at = None
        return cloned
