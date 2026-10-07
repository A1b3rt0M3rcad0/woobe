from modules.agent.infra.database.models import AgentReleaseModel, AgentReleaseTestModel
from modules.agent.infra.database.mappers import agent_release_test_model_to_entity
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentReleaseTestRepository,
)
from modules.agent.infra.database.portable_export_reader import authorize_export_read
from modules.agent.domain.entities import AgentReleaseTest
from modules.agent.domain.enums import ReleaseTestStatus
from shared.contracts.errors import ValidationError, NotFoundError


class SQLReleaseTestExecutionStore:
    def __init__(self, build_uow):
        self._build_uow = build_uow

    async def prepare(self, request, principal):
        async with self._build_uow() as uow:
            await authorize_export_read(
                uow.session,
                principal,
                request.project_id,
                "run:execute",
                identifiers={
                    "agent_id": str(request.agent_id),
                    "release_id": str(request.release_id),
                },
            )
            release = await uow.session.get(AgentReleaseModel, request.release_id)
            if (
                release is None
                or release.project_id != request.project_id
                or release.agent_id != request.agent_id
            ):
                raise NotFoundError("Test snapshot is unavailable")
            if (
                request.environment in {"release", "production"}
                and release.snapshot_kind != "release"
            ):
                raise ValidationError("Release testing requires an immutable Release")
            if request.environment == "staging" and release.snapshot_kind != "staging":
                raise ValidationError("Staging testing requires a Staging snapshot")
            if request.environment == "draft" and release.snapshot_kind != "draft":
                raise ValidationError("Draft testing requires a Draft snapshot")
            repository = SQLAlchemyAgentReleaseTestRepository(uow)
            return await repository.save(
                AgentReleaseTest(
                    project_id=request.project_id,
                    agent_id=request.agent_id,
                    release_id=request.release_id,
                    contract_version_id=release.contract_version_id,
                    input_payload={
                        "message": request.message,
                        "external_context": request.external_context,
                    },
                    expected_output=request.expected_output,
                )
            )

    async def finish(self, test_id, *, actual_output, errors, latency_ms):
        async with self._build_uow() as uow:
            test = await uow.session.get(AgentReleaseTestModel, test_id, with_for_update=True)
            if test is None:
                raise NotFoundError("Release test is unavailable")
            test.actual_output, test.validation_errors, test.latency_ms = (
                actual_output,
                errors or None,
                latency_ms,
            )
            test.status = (
                ReleaseTestStatus.failed.value if errors else ReleaseTestStatus.passed.value
            )
            await uow.session.flush()
            await uow.session.refresh(test)
            return agent_release_test_model_to_entity(test)
