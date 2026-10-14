"""Recheck owner revocation immediately before central material resolution."""
from sqlalchemy import select
from modules.agent.infra.database.models import ProviderCredentialModel, AgentToolModel
from modules.agent.application.interfaces.tool_types import is_mcp_tool_type
from shared.contracts.project_configuration import ConfigurationError


async def verify_configuration_consumer(session, *, project_id, consumer_kind, consumer_id):
    if consumer_kind == 'mcp_oauth':
        # Select only protocol metadata. A revoked/disconnected OAuth connection
        # cannot keep using an accepted lease through an otherwise active Tool.
        row = (await session.execute(select(AgentToolModel.status, AgentToolModel.type,
            AgentToolModel.config['oauth']['status'].astext).where(
                AgentToolModel.id == consumer_id, AgentToolModel.project_id == project_id))).one_or_none()
        if row is None or row[0] != 'active' or not is_mcp_tool_type(row[1]) or row[2] != 'connected':
            raise ConfigurationError('CONFIG_VALUE_REVOKED')
        return
    model = {'provider_credential': ProviderCredentialModel, 'tool': AgentToolModel}.get(consumer_kind)
    if model is None:
        raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
    state = await session.scalar(select(model.status).where(model.id == consumer_id, model.project_id == project_id))
    if state != 'active':
        raise ConfigurationError('CONFIG_VALUE_REVOKED')
