"""Owner-side, authorized resource evidence for the development registry."""

from datetime import UTC
from uuid import UUID

from sqlalchemy import select

from modules.agent.infra.database.models import (
    AgentModel,
    AgentReleaseModel,
    AgentToolModel,
    AgentPromptModel,
    AgentContractModel,
)
from modules.agent.infra.database.mappers import model_to_tool
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.agent.infra.database.skill_models import SkillVersionModel, SkillModel
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel
from modules.agent.infra.database.portable_export_reader import authorize_export_read
from shared.contracts.errors import NotFoundError, ValidationError


def revision_time(row):
    value = row.updated_at
    return value.replace(tzinfo=value.tzinfo or UTC).isoformat() if value else "initial"


class DevelopmentResourceReader:
    def __init__(self, tool_projection):
        self._tool_projection = tool_projection

    async def inspect(
        self, session, *, project_id, principal, kind, resource_id, lock=False, environment=None, required_permission=None
    ):
        models = {
            "Agent": (AgentModel, "agent:read", "agent_id"),
            "Tool": (AgentToolModel, "tool:read", "tool_id"),
            "Model": (ProviderModelModel, "model:read", "provider_model_id"),
            "Skill": (SkillVersionModel, "skill:read", "skill_version_id"),
            "Knowledge": (VectorSnapshotModel, "knowledge:read", "snapshot_id"),
            "Prompt": (AgentPromptModel, "agent:read", "prompt_id"),
            "Contract": (AgentContractModel, "agent:read", "contract_id"),
        }
        if kind not in models:
            raise ValidationError("Unsupported development resource kind")
        model, permission, parameter = models[kind]
        permission = required_permission or permission
        await authorize_export_read(
            session,
            principal,
            project_id,
            permission,
            identifiers={parameter: str(resource_id), **({"environment": environment} if environment else {})},
        )
        row = await session.get(
            model, UUID(str(resource_id)), with_for_update=lock, populate_existing=lock
        )
        owner = row
        if kind == "Skill" and row is not None:
            owner = await session.get(SkillModel, row.skill_id, with_for_update=lock)
        if (
            row is None
            or owner is None
            or owner.project_id != project_id
            or getattr(row, "status", None) == "archived"
        ):
            raise NotFoundError("Development resource is unavailable")
        result = {
            "resource_id": str(row.id),
            "kind": kind,
            "revision": revision_time(row),
        }
        if kind == "Agent":
            draft = await session.scalar(
                select(AgentReleaseModel)
                .where(
                    AgentReleaseModel.agent_id == row.id,
                    AgentReleaseModel.snapshot_kind == "draft",
                )
                .order_by(
                    AgentReleaseModel.updated_at.desc(), AgentReleaseModel.id.desc()
                )
                .limit(1)
            )
            result.update(
                revision=row.revision, draft_id=str(draft.id) if draft else None
            )
        elif kind == "Tool":
            result["owner_agent_id"] = str(row.agent_id) if row.agent_id else None
            result["portable_tool"] = self._tool_projection(model_to_tool(row))
        elif kind == "Knowledge":
            result.update(
                revision=row.snapshot_hash,
                collection_id=str(row.collection_id),
                status=row.status,
            )
        elif kind == "Skill":
            result.update(
                revision=row.package_hash,
                skill_id=str(row.skill_id),
                version=row.version,
            )
        elif kind in {"Prompt", "Contract"}:
            result["owner_agent_id"] = str(row.agent_id)
        return result
