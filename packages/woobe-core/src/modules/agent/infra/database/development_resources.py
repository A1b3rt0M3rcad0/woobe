from uuid import UUID
from sqlalchemy import select
from modules.agent.domain.release_snapshot import release_snapshot_hash
from modules.agent.infra.database.models import (
    AgentModel,
    AgentReleaseModel,
    AgentPromptModel,
    AgentContractModel,
    DocumentCollectionModel,
    DocumentModel,
)
from shared.contracts.errors import NotFoundError, ConflictError


class SQLDevelopmentResources:
    def __init__(self, uow, reader):
        self._uow, self._reader = uow, reader

    async def prepare_existing(self, data, agent_id):
        agent = await self._uow.session.get(
            AgentModel, UUID(agent_id), with_for_update=True
        )
        if agent is None or str(agent.project_id) != data["project_id"]:
            raise NotFoundError("Agent is unavailable")
        if agent.status == "archived":
            raise ConflictError("Archived Agents must be restored explicitly")
        return {"id": str(agent.id), "revision": agent.revision}

    async def reuse(self, data, principal):
        evidence = await self._reader.inspect(
            self._uow.session,
            project_id=UUID(data["project_id"]),
            principal=principal,
            kind=data["kind"],
            resource_id=data["resource_id"],
            lock=True,
        )
        if str(evidence["revision"]) != str(data["expected_revision"]):
            raise ConflictError("Resource changed after synchronization planning")
        result = {"id": evidence["resource_id"]}
        if data["kind"] == "Agent":
            if not evidence.get("draft_id"):
                raise ConflictError("Agent has no saved Draft to reuse")
            result.update(id=evidence["draft_id"], agent_id=evidence["resource_id"])
        elif data["kind"] == "Skill":
            result.update(
                skill_id=evidence["skill_id"],
                version=evidence["version"],
                package_hash=evidence["revision"],
            )
        elif data["kind"] == "Knowledge":
            if evidence["status"] != "READY":
                raise ConflictError("Knowledge snapshot is not ready")
            result.update(
                vector_snapshot_id=evidence["resource_id"],
                collection_id=evidence["collection_id"],
                status="READY",
            )
        return result

    async def reuse_frozen(self, data, principal):
        await self._reader.inspect(
            self._uow.session,
            project_id=UUID(data["project_id"]),
            principal=principal,
            kind="Agent",
            resource_id=data["agent_id"],
        )
        row = await self._uow.session.get(AgentReleaseModel, UUID(data["release_id"]))
        if (
            row is None
            or str(row.project_id) != data["project_id"]
            or str(row.agent_id) != data["agent_id"]
            or release_snapshot_hash(row) != data["snapshot_digest"]
        ):
            raise ConflictError("Frozen Agent snapshot changed after export")
        return {
            "id": str(row.id),
            "agent_id": str(row.agent_id),
            "configuration_ready": True,
            "execution_ready": False,
            "lifecycle_state": row.snapshot_kind,
        }

    async def find_artifact(self, kind, data):
        if kind == "Collection":
            identifier = data.get("development_collection_id")
            if not identifier:
                return None
            row = await self._uow.session.get(
                DocumentCollectionModel, UUID(identifier), with_for_update=True
            )
            if (
                row is not None
                and str(row.project_id) == data["project_id"]
                and row.status == "active"
                and row.name == data["name"]
                and (row.description or "") == (data.get("description") or "")
            ):
                return {"id": str(row.id)}
            return None
        if kind == "Document":
            rows = (
                await self._uow.session.scalars(
                    select(DocumentModel).where(
                        DocumentModel.project_id == UUID(data["project_id"]),
                        DocumentModel.collection_id == UUID(data["collection_id"]),
                        DocumentModel.sha256 == data["sha256"],
                    )
                )
            ).all()
            fields = ("title", "file_name", "content_type", "size_bytes", "parser")
            for row in rows:
                if row.status not in {"failed", "deleted", "archived"} and all(
                    getattr(row, field) == data[field] for field in fields
                ):
                    return {"id": str(row.id)}
            return None
        model = AgentPromptModel if kind == "Prompt" else AgentContractModel
        fields = (
            ("version", "name", "content", "content_hash")
            if kind == "Prompt"
            else (
                "version",
                "name",
                "input_schema",
                "output_schema",
                "validation_mode",
                "repair_attempts",
                "additional_instructions",
                "schema_hash",
            )
        )
        rows = (
            await self._uow.session.scalars(
                select(model).where(
                    model.project_id == UUID(data["project_id"]),
                    model.agent_id == UUID(data["agent_id"]),
                    model.version == data["version"],
                )
            )
        ).all()
        for row in rows:
            if all(getattr(row, field) == data.get(field) for field in fields):
                return {"id": str(row.id)}
        return None
