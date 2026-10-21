"""Metadata-only projection for independently accepted model operations."""
from dataclasses import replace
from urllib.parse import urlsplit

from sqlalchemy import select

from modules.agent.application.interfaces.model_spec_compatibility import LegacyModelSpecResolver
from modules.agent.domain.entities import ProviderCredential, ProviderModel
from modules.agent.domain.model_spec import ModelModalities, ModelOperations, ModelSpec, ModelTypes, model_spec_hash
from modules.agent.infra.adapters.configuration_bindings import provider_dependencies, provider_destination
from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from shared.contracts.project_configuration import ConfigurationError, compile_authentication
from shared.contracts.llm_cost import provider_model_pricing_snapshot


class OperationModelBindingRepository:
    def __init__(self, session):
        # The host's existing UoW owns this session and its short transaction.
        self._session = session

    async def metadata(self, project_id, model_id, *, lock=False):
        query = select(ProviderModelModel).where(ProviderModelModel.id == model_id,
            ProviderModelModel.project_id == project_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        model = await self._session.scalar(query)
        if model is None or model.status != 'active':
            raise ConfigurationError('CONFIG_REFERENCE_NOT_FOUND')
        # Ciphertext is deliberately excluded, including for a legacy credential
        # that this operation will reject instead of silently consuming it.
        query = select(ProviderCredentialModel.id, ProviderCredentialModel.project_id,
            ProviderCredentialModel.provider, ProviderCredentialModel.name,
            ProviderCredentialModel.authentication, ProviderCredentialModel.binding_revision,
            ProviderCredentialModel.status, ProviderCredentialModel.meta).where(
                ProviderCredentialModel.id == model.provider_credential_id,
                ProviderCredentialModel.project_id == project_id)
        if lock:
            query = query.with_for_update()
        row = (await self._session.execute(query)).one_or_none()
        if row is None or row.status != 'active':
            raise ConfigurationError('CONFIG_VALUE_REVOKED')
        credential = ProviderCredential(id=row.id, project_id=row.project_id, provider=row.provider,
            name=row.name, authentication=row.authentication, binding_revision=row.binding_revision,
            metadata=row.meta or {})
        authentication = compile_authentication(credential.authentication, allow_legacy=False)
        if authentication['type'] not in {'api_key', 'bearer'}:
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        destination = provider_destination(credential)
        parsed = urlsplit(destination)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment):
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        entity = ProviderModel(id=model.id, project_id=project_id, model=model.model,
            model_type=model.model_type, spec=model.spec, metadata=model.meta or {})
        spec = ModelSpec.from_dict(model.spec) if model.spec is not None else LegacyModelSpecResolver().resolve(
            entity, provider=str(credential.provider))
        digest = model_spec_hash(spec)
        if (model.spec_hash is not None and model.spec_hash != digest
            or spec.provider != str(credential.provider) or spec.model_id != model.model
            or spec.model_type != ModelTypes.LANGUAGE or not spec.supports_operation(ModelOperations.LANGUAGE_GENERATE)
            or not spec.accepts(ModelModalities.TEXT) or not spec.produces(ModelModalities.TEXT)):
            raise ConfigurationError('CONFIG_DEFINITION_INVALID')
        # Preserve only semantic runtime/pricing fields. Provider discovery's raw
        # response metadata is not part of the accepted operation snapshot.
        safe_spec = replace(spec, metadata={}, pricing={}, capabilities={name: replace(capability, config={})
            for name, capability in spec.capabilities.items()}).as_dict()
        return {'definition': {'project_id': str(project_id), 'model_id': str(model.id),
            'model_revision': model.definition_revision, 'model_spec': safe_spec, 'spec_hash': digest,
            'provider': str(credential.provider), 'model': model.model,
            'credential_id': str(credential.id), 'credential_binding_revision': credential.binding_revision,
            'destination': destination, 'pricing_snapshot': provider_model_pricing_snapshot(
                provider_model_id=model.id, provider_credential_id=credential.id, provider=credential.provider,
                model=model.model, metadata={**(model.meta or {}), **({'pricing': dict(spec.pricing)} if spec.pricing else {})})}, 'dependencies': provider_dependencies(credential, base_url=destination)}
