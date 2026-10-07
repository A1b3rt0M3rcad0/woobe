from modules.agent.infra.database.development_resource_reader import (
    DevelopmentResourceReader,
)
from modules.agent.infra.database.models import AgentModel
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.composition.resources import DATABASE_ENGINE
from shared.contracts.errors import NotFoundError, ConflictError
from shared.presentation.contracts import OperationResult
from shared.infra.transactional_handler import TransactionalHandler
from uuid import UUID


def build_development_resource_reader():
    return DevelopmentResourceReader()


def prepare_existing_agent_composer():
    uow = AgentUnitOfWork(DATABASE_ENGINE)

    async def handle(request):
        agent = await uow.session.get(
            AgentModel, UUID(request.path_params["agent_id"]), with_for_update=True
        )
        if agent is None or str(agent.project_id) != request.body["project_id"]:
            raise NotFoundError("Agent is unavailable")
        if agent.status == "archived":
            raise ConflictError("Archived Agents must be restored explicitly")
        return OperationResult(
            body={
                "success": True,
                "data": {"id": str(agent.id), "revision": agent.revision},
            }
        )

    return TransactionalHandler(uow, handle)


def reuse_development_resource_composer():
    uow = AgentUnitOfWork(DATABASE_ENGINE)

    async def handle(request):
        data = request.body
        evidence = await DevelopmentResourceReader().inspect(
            uow.session,
            project_id=UUID(data["project_id"]),
            principal=request.principal,
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
        elif data["kind"] == "Knowledge":
            if evidence["status"] != "READY":
                raise ConflictError("Knowledge snapshot is not ready")
            result.update(
                vector_snapshot_id=evidence["resource_id"],
                collection_id=evidence["collection_id"],
                status="READY",
            )
        return OperationResult(body={"success": True, "data": result})

    return TransactionalHandler(uow, handle)


def reuse_frozen_agent_composer():
    from modules.agent.infra.database.models import AgentReleaseModel
    from modules.agent.domain.release_snapshot import release_snapshot_hash

    uow = AgentUnitOfWork(DATABASE_ENGINE)

    async def handle(request):
        data = request.body
        await DevelopmentResourceReader().inspect(
            uow.session,
            project_id=UUID(data["project_id"]),
            principal=request.principal,
            kind="Agent",
            resource_id=data["agent_id"],
        )
        row = await uow.session.get(AgentReleaseModel, UUID(data["release_id"]))
        if (
            row is None
            or str(row.project_id) != data["project_id"]
            or str(row.agent_id) != data["agent_id"]
            or release_snapshot_hash(row) != data["snapshot_digest"]
        ):
            raise ConflictError("Frozen Agent snapshot changed after export")
        return OperationResult(
            body={
                "success": True,
                "data": {
                    "id": str(row.id),
                    "agent_id": str(row.agent_id),
                    "configuration_ready": True,
                    "execution_ready": False,
                    "lifecycle_state": row.snapshot_kind,
                },
            }
        )

    return TransactionalHandler(uow, handle)


def materialize_development_artifact_composer(kind):
    from sqlalchemy import select
    from modules.agent.infra.database.models import AgentPromptModel, AgentContractModel
    from modules.agent.infra.database.repositories import (
        SQLAlchemyAgentPromptRepository,
        SQLAlchemyAgentContractRepository,
    )
    from modules.agent.application.use_cases.ai_prompt_cases import CreatePromptUseCase
    from modules.agent.application.use_cases.ai_contract_cases import (
        CreateContractUseCase,
    )
    from modules.agent.presentation.controllers.create_prompt_controller import (
        CreatePromptController,
    )
    from modules.agent.presentation.controllers.create_contract_controller import (
        CreateContractController,
    )

    uow = AgentUnitOfWork(DATABASE_ENGINE)
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
    controller = (
        CreatePromptController(
            CreatePromptUseCase(SQLAlchemyAgentPromptRepository(uow))
        )
        if kind == "Prompt"
        else CreateContractController(
            CreateContractUseCase(SQLAlchemyAgentContractRepository(uow))
        )
    )

    async def handle(request):
        data = request.body
        rows = (
            await uow.session.scalars(
                select(model).where(
                    model.project_id == UUID(data["project_id"]),
                    model.agent_id == UUID(data["agent_id"]),
                    model.version == data["version"],
                )
            )
        ).all()
        for row in rows:
            if all(getattr(row, field) == data.get(field) for field in fields):
                return OperationResult(
                    body={"success": True, "data": {"id": str(row.id)}}
                )
        return await controller.handle(request)

    return TransactionalHandler(uow, handle)
