"""Recheck owner revocation immediately before central material resolution."""
from sqlalchemy import select
from modules.agent.infra.database.models import ProviderCredentialModel, AgentToolModel
from shared.contracts.project_configuration import ConfigurationError


async def verify_configuration_consumer(session, *, project_id, consumer_kind, consumer_id):
    model = {'provider_credential': ProviderCredentialModel, 'tool': AgentToolModel}.get(consumer_kind)
    if model is None:
        raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
    state = await session.scalar(select(model.status).where(model.id == consumer_id, model.project_id == project_id))
    if state != 'active':
        raise ConfigurationError('CONFIG_VALUE_REVOKED')
