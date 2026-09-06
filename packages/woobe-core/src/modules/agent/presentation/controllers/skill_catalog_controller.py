from dataclasses import asdict
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from modules.agent.application.skill_packages import ImportSkillInput
from modules.agent.application.use_cases.skill_cases import SkillCatalog
from modules.agent.domain.skills import SkillVersion
from shared.presentation.contracts import (
    OperationOutcome,
    OperationRequest,
    OperationResult,
)


class SkillListQuery(BaseModel):
    query: str = Field(default="", max_length=200)
    offset: int = Field(default=0, ge=0, le=1_000_000)
    limit: int = Field(default=50, ge=1, le=100)


def version_summary(version: SkillVersion) -> dict:
    return {
        "id": str(version.id),
        "skill_id": str(version.skill_id),
        "version": version.version,
        "package_hash": version.package_hash,
        "name": version.package["name"],
        "description": version.package["description"],
        "required_tools": version.package["required_tools"],
        "estimated_instruction_units": max(
            1, (len(version.package["instructions"]) + 3) // 4
        ),
        "resource_paths": sorted(version.package["resources"]),
        "created_at": version.created_at,
    }


class SkillCatalogController:
    def __init__(
        self,
        catalog: SkillCatalog,
        operation: Literal["list", "create", "versions", "add_version", "get_version"],
    ) -> None:
        self._catalog = catalog
        self._operation = operation

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = UUID(str(request.path_params["project_id"]))
        query = SkillListQuery.model_validate(request.query_params)
        created = False
        if self._operation == "list":
            data = [
                asdict(item)
                for item in await self._catalog.list(project_id, **query.model_dump())
            ]
        elif self._operation == "versions":
            skill_id = UUID(str(request.path_params["skill_id"]))
            data = [
                version_summary(item)
                for item in await self._catalog.versions(
                    project_id, skill_id, offset=query.offset, limit=query.limit
                )
            ]
        elif self._operation == "get_version":
            version = await self._catalog.get_version(
                project_id, UUID(str(request.path_params["skill_version_id"]))
            )
            data = {**version_summary(version), **version.snapshot()}
        else:
            incoming = ImportSkillInput.model_validate(request.body)
            if self._operation == "create":
                version = await self._catalog.create(project_id, incoming)
            else:
                version = await self._catalog.add_version(
                    project_id, UUID(str(request.path_params["skill_id"])), incoming
                )
            data = {**version_summary(version), **version.snapshot()}
            created = True
        return OperationResult(
            outcome=OperationOutcome.CREATED if created else OperationOutcome.SUCCESS,
            body={
                "success": True,
                "message": "created" if created else "ok",
                "data": data,
            },
        )
