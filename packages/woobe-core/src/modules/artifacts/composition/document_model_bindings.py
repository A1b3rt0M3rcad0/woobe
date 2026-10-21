"""Metadata-only bridge to the owning Agent/Core bounded contexts."""
from uuid import UUID

from shared.composition.document_model_operations import operation_model_bindings
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.project_configuration import ConfigurationError


class DocumentModelBindingRepository:
    def __init__(self, uow):
        self._uow = uow

    def _owner(self):
        return operation_model_bindings(self._uow.session)

    async def freeze(self, request):
        reference = request.reference
        try:
            return await self._owner().freeze(project_id=UUID(request.scope.project_id),
                environment=request.scope.environment.value, model_id=UUID(str(reference.model_id)),
                model_revision=reference.model_revision,
                configuration_key_id=UUID(str(reference.configuration_key_id)),
                configuration_revision=reference.configuration_revision)
        except ConfigurationError:
            raise ArtifactError('MODEL_BINDING_UNAVAILABLE', 'Requested governed model binding is unavailable') from None

    async def verify(self, snapshot, scope):
        try:
            return await self._owner().verify(snapshot, project_id=UUID(scope.project_id))
        except ConfigurationError:
            raise ArtifactError('MODEL_BINDING_UNAVAILABLE', 'Accepted governed model binding is unavailable') from None
