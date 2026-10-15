from modules.agent.application.dtos.model_discovery_dtos import (
    AvailableProviderModelOutput,
)
from modules.agent.application.use_cases.provider_model_reconciliation import (
    ReconciliationScope,
    ApplyProviderModelReconciliationInput,
    PreviewProviderModelReconciliationUseCase,
    ApplyProviderModelReconciliationUseCase,
    _digest,
    _conflict,
)
from modules.agent.application.interfaces.project_configuration import (
    configuration_for_session,
)
from modules.agent.infra.adapters.configuration_bindings import provider_dependencies
from modules.agent.infra.adapters.provider_discovery_handler import (
    authorize_provider_models,
)
from modules.agent.infra.database.provider_model_repositories import (
    SQLAlchemyProviderModelRepository,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyProviderCredentialRepository,
)
from shared.contracts.errors import NotFoundError
from shared.presentation.contracts import OperationRequest, OperationResult


class ProviderModelReconciliationHandler:
    def __init__(self, uow_factory, discovery, *, apply=False):
        self.uow_factory, self.discovery, self.apply = uow_factory, discovery, apply

    async def __call__(self, request):
        dto = (
            ApplyProviderModelReconciliationInput.model_validate(request.body)
            if self.apply
            else ReconciliationScope.model_validate(request.query_params)
        )
        scope = ReconciliationScope(
            **dto.model_dump(include=set(ReconciliationScope.model_fields))
        )
        discovered = await self.discovery(
            OperationRequest(
                principal=request.principal,
                query_params={
                    "project_id": str(dto.project_id),
                    "available_for_credential_id": str(dto.provider_credential_id),
                    "environment": dto.environment,
                    "capability": "embedding"
                    if dto.capability == "embedding"
                    else None,
                },
            )
        )
        remote = [
            AvailableProviderModelOutput.model_validate(item)
            for item in discovered.body["data"]
        ]
        revision = int(discovered.metadata["credential_binding_revision"])
        configuration_revision = discovered.metadata["configuration_revision"]
        # No external I/O or secret resolution in this transaction.
        uow = self.uow_factory()
        if not self.apply:
            uow.mark_read_only()
        async with uow:
            credentials = SQLAlchemyProviderCredentialRepository(uow)
            credential = await credentials.get_by_id(dto.provider_credential_id)
            if credential is None or credential.project_id != dto.project_id:
                raise NotFoundError("Provider credential not found")
            permissions = ["model:read", "provider:read"] + (
                ["model:write"] if self.apply else []
            )
            await authorize_provider_models(
                uow.session, request.principal, credential, dto.environment, permissions
            )
            models = SQLAlchemyProviderModelRepository(uow)
            if self.apply:
                # Take the same owner lock as credential/configuration changes.
                credential = await credentials.lock_by_id(credential.id)
                if credential.authentication is not None:
                    configuration = configuration_for_session(uow.session)
                    if configuration is None:
                        _conflict(
                            "CONFIGURATION_REVISION_CONFLICT",
                            "Configuration store unavailable",
                        )
                    _, pins = await configuration.inspect(
                        project_id=dto.project_id,
                        environment=dto.environment,
                        dependencies=provider_dependencies(credential),
                        lock=True,
                    )
                    if (
                        _digest([pin.document() for pin in pins])
                        != configuration_revision
                    ):
                        _conflict(
                            "CONFIGURATION_REVISION_CONFLICT",
                            "Environment changed during discovery; compare again",
                        )
                result = await ApplyProviderModelReconciliationUseCase(
                    models, credentials
                ).execute(dto, remote, revision, configuration_revision)
            else:
                if credential.binding_revision != revision:
                    _conflict(
                        "CREDENTIAL_REVISION_CONFLICT",
                        "Credential changed during discovery; compare again",
                    )
                result = await PreviewProviderModelReconciliationUseCase(
                    models
                ).execute(scope, credential, remote, configuration_revision)
        return OperationResult(body={"success": True, "message": "ok", "data": result})
