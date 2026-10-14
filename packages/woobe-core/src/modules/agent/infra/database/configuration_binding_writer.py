"""Owner-controlled metadata projection and CAS reference replacement."""
from copy import deepcopy
import hashlib
import json
from sqlalchemy import select
from modules.agent.infra.database.models import ProviderCredentialModel, AgentToolModel
from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository, SQLAlchemyAgentToolRepository
from modules.agent.domain.tool_configuration import validate_tool_authentication
from shared.contracts.project_configuration import ConfigurationError, compile_authentication


def revision(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


async def configuration_binding(session, *, project_id, target_kind, target_id, authentication=None, expected_revision=None, route_id=None):
    writing = authentication is not None
    if route_id is not None and target_kind != 'tool':
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    if target_kind == "provider_credential":
        if writing:
            repo = SQLAlchemyProviderCredentialRepository(session)
            credential = await repo.lock_by_id(target_id)
            if credential is None or credential.project_id != project_id:
                raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
            if str(credential.binding_revision) != expected_revision:
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            if credential.authentication is None and credential.encrypted_secret:
                raise ConfigurationError("LEGACY_ENVIRONMENT_REQUIRED")
            compiled = compile_authentication(authentication)
            if compiled["type"] != "api_key":
                raise ConfigurationError("CONFIG_BINDING_INVALID")
            credential.authentication, credential.encrypted_secret = compiled, ""
            credential = await repo.update(credential)
            await session.flush()
            return {"target_kind": target_kind, "target_id": str(target_id), "revision": str(credential.binding_revision), "authentication": compiled}
        row = (await session.execute(select(ProviderCredentialModel.authentication, ProviderCredentialModel.binding_revision)
            .where(ProviderCredentialModel.id == target_id, ProviderCredentialModel.project_id == project_id))).one_or_none()
        if row is None:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        return {"target_kind": target_kind, "target_id": str(target_id), "revision": str(row.binding_revision), "authentication": row.authentication}
    if target_kind != "tool":
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    if writing:
        repo = SQLAlchemyAgentToolRepository(session)
        tool = await repo.lock_by_id(target_id)
        if tool.project_id != project_id:
            raise ConfigurationError('CONFIG_REFERENCE_NOT_FOUND')
        public_config = _tool_binding_view(tool.config or {})
        if revision(public_config) != expected_revision:
            raise ConfigurationError('CONFIG_REVISION_CONFLICT')
        compiled = compile_authentication(authentication, allow_none=True)
        config = deepcopy(tool.config or {})
        if route_id is None:
            config['authentication'] = compiled
        else:
            matches = [route for route in config.get('routes', []) if route.get('id') == route_id]
            if len(matches) != 1:
                raise ConfigurationError('CONFIG_REFERENCE_NOT_FOUND')
            matches[0]['authentication'] = compiled
        # Existing owner-produced compatibility scopes are verified separately
        # by the repository. The newly supplied scope uses public references only.
        validate_tool_authentication(config, allow_legacy=True)
        tool.config = config
        await repo.update(tool)
        await session.flush()
        public_config = _tool_binding_view(tool.config)
    else:
        from modules.agent.infra.database.configuration_tool_metadata import route_configuration_metadata
        row = (await session.execute(select(AgentToolModel.config['authentication'].label('authentication'),
            AgentToolModel.config['url'].astext.label('url'), AgentToolModel.config['base_url'].astext.label('base_url'),
            AgentToolModel.config['server']['url'].astext.label('server_url'), route_configuration_metadata()).where(
            AgentToolModel.project_id == project_id, AgentToolModel.id == target_id))).one_or_none()
        if row is None:
            raise ConfigurationError('CONFIG_REFERENCE_NOT_FOUND')
        public_config = dict(row._mapping)
        public_config['routes'] = [{'id': route['id'], 'path': route['path'], 'authentication': route['authentication']}
                                   for route in public_config['routes']]
    selected = public_config['authentication']
    if route_id is not None:
        matches = [route for route in public_config['routes'] if route['id'] == route_id]
        if len(matches) != 1:
            raise ConfigurationError('CONFIG_REFERENCE_NOT_FOUND')
        selected = matches[0]['authentication']
    return {'target_kind': target_kind, 'target_id': str(target_id), 'revision': revision(public_config),
            'authentication': selected, 'routes': public_config['routes'], 'route_id': route_id}


def _tool_binding_view(config):
    return {'authentication': config.get('authentication'), 'url': config.get('url'),
        'base_url': config.get('base_url'), 'server_url': (config.get('server') or {}).get('url'),
        'routes': [{'id': route.get('id'), 'path': route.get('path'),
                    'authentication': route.get('authentication')} for route in config.get('routes', [])]}
