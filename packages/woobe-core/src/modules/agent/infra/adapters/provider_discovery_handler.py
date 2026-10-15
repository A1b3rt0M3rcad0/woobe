"""Authorize and pin discovery in SQL, perform provider I/O after commit."""
from uuid import UUID, uuid4

from modules.agent.application.dtos.model_discovery_dtos import ListAvailableProviderModelsInput
from modules.agent.application.interfaces.project_configuration import configuration_for_session

from modules.agent.infra.adapters.configuration_bindings import provider_dependencies
from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
from shared.contracts.errors import AuthorizationError, NotFoundError
from shared.contracts.project_configuration import ConfigurationError
from shared.presentation.contracts import OperationOutcome, OperationResult
from shared.runtime_environment import normalize_runtime_environment
from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal
from shared.security.tenancy import TenantAuthorizer


class _CredentialSnapshot:
    def __init__(self, credential):
        self.credential = credential

    async def get_by_id(self, identifier):
        return self.credential if self.credential.id == identifier else None


async def authorize_provider_models(session, principal, credential, environment, permissions):
    authorizer = TenantAuthorizer(session)
    context = {"project_id": credential.project_id, "credential_id": credential.id, "environment": environment}
    if isinstance(principal, ControlPlanePrincipal):
        await authorizer.require_active_control(principal)
        for permission in permissions:
            await authorizer.authorize_control_key(api_key_id=principal.api_key_id, workspace_id=principal.workspace_id,
                workspace_permissions=principal.permissions, required_permission=permission,
                path_params=context, query_params={}, body=None)
    elif isinstance(principal, AuthenticatedPrincipal):
        await authorizer.require_active_human(principal)
        for permission in permissions:
            await authorizer.authorize(user_id=principal.user_id, required_permission=permission,
                path_params=context, query_params={}, body=None, mutation=permission.endswith(":write"))
    else:
        raise AuthorizationError("Administrative authentication is required")


class ProviderDiscoveryHandler:
    def __init__(self, uow_factory, *, discovery, embedding_discovery, secret_resolver, use_case_factory, additional_permissions=()):
        self.additional_permissions = additional_permissions
        self.uow_factory = uow_factory
        self.use_case_factory = use_case_factory
        self.discovery, self.embedding_discovery, self.secret_resolver = discovery, embedding_discovery, secret_resolver

    async def __call__(self, request):
        dto = ListAvailableProviderModelsInput(credential_id=UUID(str(request.path_params.get("credential_id") or request.query_params.get("available_for_credential_id"))),
            project_id=request.query_params.get("project_id"), capability=request.query_params.get("capability"))
        environment = normalize_runtime_environment(request.query_params.get("environment") or "draft")
        operation_id = uuid4()
        pins = []
        async with self.uow_factory() as uow:
            session = uow.session
            credential = await SQLAlchemyProviderCredentialRepository(session).get_by_id(dto.credential_id)
            if credential is None or (dto.project_id and credential.project_id != dto.project_id):
                raise NotFoundError("Provider credential not found")
            principal = request.principal
            permissions = ["model:read" if request.query_params.get("available_for_credential_id") else "provider:read", *self.additional_permissions]
            if credential.authentication is not None:
                permissions.append("project:environment:validate")
            await authorize_provider_models(session, principal, credential, environment, permissions)
            if credential.authentication is not None:
                configuration = configuration_for_session(session)
                if configuration is None:
                    raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
                pins = await configuration.acquire(project_id=credential.project_id, run_id=operation_id,
                    environment=environment, dependencies=provider_dependencies(credential))
        resolver = self.secret_resolver
        if credential.authentication is not None:
            project_id, credential_id = credential.project_id, credential.id
            async def resolve_destination(destination):
                async with self.uow_factory().mark_read_only() as uow:
                    session = uow.session
                    live = await SQLAlchemyProviderCredentialRepository(session).get_by_id(credential_id)
                    if live is None or live.project_id != project_id or getattr(live.status, "value", live.status) != "active":
                        raise ConfigurationError("CONFIG_VALUE_REVOKED")
                    configuration = configuration_for_session(session)
                    if configuration is None:
                        raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
                    return await configuration.resolve(project_id=project_id, run_id=operation_id,
                        consumer_kind="provider_credential", consumer_id=credential_id,
                        field_path="/authentication/fields/api_key", destination=destination)
            bound = BoundConfigurationCredential(resolve_destination)
            resolver = lambda _encrypted: bound
        use_case = self.use_case_factory(credential_repo=_CredentialSnapshot(credential),
            discovery=self.discovery, embedding_discovery=self.embedding_discovery, resolve_secret=resolver)
        state = "unknown"
        try:
            items = await use_case.execute(dto)
            state = "valid"
        finally:
            if credential.authentication is not None:
                # Evidence belongs to the accepted versions, so rotation makes
                # it stale. Never persist upstream bodies, headers or messages.
                async with self.uow_factory() as uow:
                    configuration = configuration_for_session(uow.session)
                    if configuration is not None:
                        await configuration.record_validation(project_id=credential.project_id,
                            run_id=operation_id, consumer_kind="provider_credential", consumer_id=credential.id,
                            state=state, actor="key:" + str(principal.api_key_id) if isinstance(principal, ControlPlanePrincipal)
                            else "user:" + str(principal.user_id))
        from modules.agent.domain.catalog_reconciliation import catalog_digest
        return OperationResult(outcome=OperationOutcome.SUCCESS,
            metadata={"credential_binding_revision": str(credential.binding_revision), "configuration_revision": catalog_digest(pins)},
            body={"success": True, "message": "ok", "data": [item.model_dump() for item in items]})
