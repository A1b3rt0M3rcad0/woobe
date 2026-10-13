"""Authorize and queue a structural vector intent without external I/O."""
from modules.agent.application.vector_configuration import verify_vector_configuration
from sqlalchemy import select
from modules.agent.application.dtos.vector_preparation_dtos import PrepareVectorSnapshotInput
from modules.agent.application.interfaces.project_configuration import configuration_for_session
from modules.agent.infra.adapters.configuration_bindings import provider_dependencies
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyProviderModelRepository
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel
from shared.contracts.errors import ConflictError, NotFoundError
from shared.contracts.project_configuration import ConfigurationError
from shared.presentation.contracts import OperationResult, OperationOutcome


class PrepareVectorSnapshot:
    def __init__(self, uow):
        self.uow = uow

    async def __call__(self, request):
        definition = PrepareVectorSnapshotInput.model_validate({**request.body, "snapshot_id": request.path_params["snapshot_id"]})
        session = self.uow.session
        snapshot = await session.scalar(select(VectorSnapshotModel).where(
            VectorSnapshotModel.id == definition.snapshot_id, VectorSnapshotModel.project_id == definition.project_id).with_for_update())
        if snapshot is None:
            raise NotFoundError("Vector snapshot is unavailable")
        if snapshot.build_config_hash != definition.expected_build_config_hash:
            raise ConflictError("Vector build definition changed")
        if snapshot.status != "PENDING_PREPARATION":
            if snapshot.status in {"BUILDING", "READY"} and (snapshot.preparation_environment or "draft") == definition.environment:
                return self._result(snapshot)
            raise ConflictError("Vector snapshot cannot resume this preparation; create a new version")
        model = await SQLAlchemyProviderModelRepository(self.uow).get_by_id(snapshot.embedding_provider_model_id)
        if model is None or model.project_id != definition.project_id or str(getattr(model.status, "value", model.status)) != "active":
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        credential = await SQLAlchemyProviderCredentialRepository(self.uow).get_by_id(model.provider_credential_id)
        if credential is None or credential.project_id != definition.project_id or str(getattr(credential.status, "value", credential.status)) != "active":
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        verify_vector_configuration(snapshot, model, credential)
        if credential.authentication is not None:
            port = configuration_for_session(session)
            if port is None:
                raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
            await port.acquire(project_id=definition.project_id, run_id=snapshot.id, environment=definition.environment,
                dependencies=provider_dependencies(credential, base_url=(model.metadata or {}).get("base_url")))
        snapshot.preparation_environment = definition.environment
        snapshot.status, snapshot.build_stage = "BUILDING", "QUEUED"
        await session.flush()
        return self._result(snapshot)

    @staticmethod
    def _result(snapshot):
        return OperationResult(outcome=OperationOutcome.ACCEPTED,
            body={"success": True, "data": {"id": str(snapshot.id), "status": snapshot.status,
                "build_config_hash": snapshot.build_config_hash, "environment": (snapshot.preparation_environment or "draft"),
                "runtime_preparation_status": "ready" if snapshot.status == "READY" else "pending"}})
