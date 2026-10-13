from sqlalchemy import text

from modules.agent.infra.database.models import AgentReleaseModel, AgentReleaseTestModel
from modules.agent.infra.database.mappers import agent_release_test_model_to_entity
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentReleaseTestRepository,
)
from modules.agent.infra.database.portable_export_reader import authorize_export_read
from modules.agent.domain.entities import AgentReleaseTest
from modules.agent.domain.enums import ReleaseTestStatus
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError
from modules.agent.infra.database.asac_environment_selector import (
    selected_agent_release,
)


class SQLReleaseTestExecutionStore:
    def __init__(self, build_uow, *, build_snapshot):
        self._build_uow = build_uow
        self._build_snapshot = build_snapshot

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
            identity = getattr(request, "test_id", None)
            if identity is not None:
                # Serialize only admission of the same request identity, never hold
                # a database transaction across provider execution.
                await uow.session.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                                          {"key": identity.int & ((1 << 63) - 1)})
                existing = await uow.session.get(AgentReleaseTestModel, identity)
                if existing is not None:
                    if existing.project_id != request.project_id or existing.agent_id != request.agent_id:
                        raise NotFoundError("Release test is unavailable")
                    if (existing.release_id != request.release_id or existing.expected_output != request.expected_output
                        or existing.input_payload != {"message": request.message, "external_context": request.external_context, "environment": request.environment}):
                        raise ConflictError("Release test identity already belongs to another request")
                    test = agent_release_test_model_to_entity(existing)
                    test.replayed = True
                    return test
            release = await uow.session.get(AgentReleaseModel, request.release_id)
            selected = None
            if request.environment in {"staging", "production"}:
                selected = await selected_agent_release(
                    uow.session, request.agent_id, request.environment, lock=True
                )
                if selected is not None and selected.id != request.release_id:
                    raise ConflictError("ASAC_TEST_SELECTION_CHANGED")
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
            if (
                request.environment == "staging"
                and selected is None
                and release.snapshot_kind != "staging"
            ):
                raise ValidationError("Staging testing requires a Staging snapshot")
            if request.environment == "draft" and release.snapshot_kind != "draft":
                raise ValidationError("Draft testing requires a Draft snapshot")
            repository = SQLAlchemyAgentReleaseTestRepository(uow)
            test = await repository.save(
                AgentReleaseTest(
                    **({"id": identity} if identity is not None else {}),
                    project_id=request.project_id,
                    agent_id=request.agent_id,
                    release_id=request.release_id,
                    contract_version_id=release.contract_version_id,
                    input_payload={
                        "environment": request.environment,
                        "message": request.message,
                        "external_context": request.external_context,
                    },
                    expected_output=request.expected_output,
                )
            )
            test.execution_snapshot = self._build_snapshot(release)
            test.validation_schema = getattr(release, "output_schema", None)
            response = getattr(release, "response_format", None) or {}
            if test.validation_schema is None and not release.contract_version_id:
                test.validation_schema = response.get("schema") if response.get("enabled") else None
            test.contract_missing = bool(release.contract_version_id and test.validation_schema is None)
            return test

    async def finish(self, test_id, *, actual_output, errors, latency_ms):
        async with self._build_uow() as uow:
            test = await uow.session.get(
                AgentReleaseTestModel, test_id, with_for_update=True
            )
            if test is None:
                raise NotFoundError("Release test is unavailable")
            test.actual_output, test.validation_errors, test.latency_ms = (
                actual_output,
                errors or None,
                latency_ms,
            )
            test.status = (
                ReleaseTestStatus.failed.value
                if errors
                else ReleaseTestStatus.passed.value
            )
            await uow.session.flush()
            await uow.session.refresh(test)
            return agent_release_test_model_to_entity(test)
