"""Closed OAuth material fields and destinations, separate from public metadata."""
import hashlib
import json
from uuid import UUID

from modules.agent.domain.tool_configuration import tool_destination
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError, compile_authentication

OAUTH_FIELDS = frozenset({'access_token', 'refresh_token', 'client_secret', 'code_verifier', 'device_code'})
OAUTH_FIELD_PREFIX = '/config/oauth/fields/'
OAUTH_PRIVATE_HANDLE = 'woobe-oauth-ref:'


def oauth_references(config):
    oauth = config.get('oauth') or {}
    if not isinstance(oauth, dict):
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    references = oauth.get('configuration_refs') or {}
    if not isinstance(references, dict) or set(references) - OAUTH_FIELDS:
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    if not references:
        return {}
    return compile_authentication({'type': 'headers', 'fields': references}, allow_legacy=True)['fields']


def oauth_destination(config, field):
    if field not in OAUTH_FIELDS:
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    oauth = config.get('oauth') or {}
    raw = ((config.get('server') or {}).get('url') or config.get('url')) if field == 'access_token' else oauth.get('token_endpoint')
    return tool_destination(raw)


def oauth_dependencies(tool, *, fields=None, impact=()):
    config = tool.config or {}
    references = oauth_references(config)
    if not references:
        return []
    selected = set(references) if fields is None else set(fields)
    if selected - OAUTH_FIELDS:
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    oauth = config['oauth']
    identity = {'references': references, 'mcp_destination': ((config.get('server') or {}).get('url') or config.get('url')),
        'token_endpoint': oauth.get('token_endpoint'), 'client_id': oauth.get('client_id'),
        'resource': oauth.get('resource'), 'scopes': oauth.get('scopes') or [],
        'token_endpoint_auth_method': oauth.get('token_endpoint_auth_method')}
    revision = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return [ConfigurationDependency(tool.project_id, 'mcp_oauth', tool.id, revision,
        OAUTH_FIELD_PREFIX + field, references[field]['key'], oauth_destination(config, field), impact=impact,
        legacy_alias_id=UUID(references[field]['alias_id']) if references[field]['source'] == 'legacy_configuration' else None)
        for field in sorted(selected & set(references))]


def hydrate_oauth_workset(tool):
    """Request-local compatibility shape; handles contain no encrypted material."""
    from copy import deepcopy
    result = deepcopy(tool)
    references = oauth_references(result.config or {})
    if not references:
        return result
    oauth = result.config['oauth']
    if any(field + '_encrypted' in oauth for field in OAUTH_FIELDS):
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    oauth.pop('configuration_refs')
    for field, reference in references.items():
        # Public Environment references need a resolver identity too. The alias
        # handle is strictly an owner-to-cipher compatibility token, not a URI.
        if reference['source'] != 'legacy_configuration':
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        oauth[field + '_encrypted'] = OAUTH_PRIVATE_HANDLE + reference['alias_id']
    return result
