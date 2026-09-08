from uuid import UUID

from modules.agent.application.dtos.skill_dtos import (
    ImportSkillInput,
    SkillListQuery,
    SkillSummary,
)
from modules.agent.application.interfaces.skill_catalog import SkillCatalogOperations
from modules.agent.domain.skills import SkillVersion
from shared.presentation.contracts import (
    OperationOutcome,
    OperationRequest,
    OperationResult,
)


def _estimated_instruction_units(version: SkillVersion) -> int:
    return max(1, (len(version.package["instructions"]) + 3) // 4)


def version_summary(version: SkillVersion) -> dict:
    return {
        "id": str(version.id),
        "skill_id": str(version.skill_id),
        "version": version.version,
        "package_hash": version.package_hash,
        "name": version.package["name"],
        "description": version.package["description"],
        "required_tools": version.package["required_tools"],
        "estimated_instruction_units": _estimated_instruction_units(version),
        "resource_paths": sorted(version.package["resources"]),
        "created_at": version.created_at,
    }


def skill_summary(summary: SkillSummary) -> dict:
    latest = summary.latest_version
    return {
        "id": str(summary.skill.id),
        "project_id": str(summary.skill.project_id),
        "name": summary.skill.name,
        "created_at": summary.skill.created_at,
        "latest_version_id": str(latest.id) if latest else None,
        "latest_version": latest.version if latest else None,
        "latest_description": latest.package["description"] if latest else None,
        "latest_required_tools": list(latest.package["required_tools"]) if latest else [],
        "latest_estimated_instruction_units": (
            _estimated_instruction_units(latest) if latest else None
        ),
        "latest_resource_count": len(latest.package["resources"]) if latest else 0,
        "latest_version_created_at": latest.created_at if latest else None,
        "version_count": summary.version_count,
    }


class SkillCatalogController:
    def __init__(self, catalog: SkillCatalogOperations) -> None:
        self._catalog = catalog

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = UUID(str(request.path_params["project_id"]))
        operation = str(request.metadata.get("skill_operation") or "")
        query = SkillListQuery.model_validate(request.query_params)
        created = False
        if operation == "list":
            data = [
                skill_summary(item)
                for item in await self._catalog.list(project_id, **query.model_dump())
            ]
        elif operation == "versions":
            skill_id = UUID(str(request.path_params["skill_id"]))
            data = [
                version_summary(item)
                for item in await self._catalog.versions(
                    project_id, skill_id, offset=query.offset, limit=query.limit
                )
            ]
        elif operation == "get_version":
            version = await self._catalog.get_version(
                project_id, UUID(str(request.path_params["skill_version_id"]))
            )
            data = {**version_summary(version), **version.snapshot()}
        elif operation in {"create", "add_version"}:
            incoming = ImportSkillInput.model_validate(request.body)
            if operation == "create":
                version = await self._catalog.create(project_id, incoming)
            else:
                version = await self._catalog.add_version(
                    project_id, UUID(str(request.path_params["skill_id"])), incoming
                )
            data = {**version_summary(version), **version.snapshot()}
            created = True
        else:
            raise ValueError("Unknown Skill catalog operation")
        return OperationResult(
            outcome=OperationOutcome.CREATED if created else OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "created" if created else "ok",
                "data": data,
            },
        )
