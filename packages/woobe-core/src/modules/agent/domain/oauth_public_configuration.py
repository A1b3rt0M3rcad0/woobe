"""Public OAuth metadata and safe edits of an opaque, flow-owned source."""
from copy import deepcopy

from modules.agent.domain.oauth_configuration import OAUTH_FIELDS
from shared.contracts.project_configuration import ConfigurationError


def _private_field(name):
    return not isinstance(name, str) or name in OAUTH_FIELDS | {'state', 'code', 'authorization_code'} or name.endswith('_encrypted')


def public_tool_configuration(config, *, tool_type=None):
    if config is None:
        return None
    public = deepcopy(config)
    if getattr(tool_type, 'value', tool_type) in {'mcp', 'http_mcp'}:
        public.setdefault('protocol', 'mcp')
    oauth = public.get('oauth')
    if isinstance(oauth, dict):
        public['oauth'] = {name: value for name, value in oauth.items() if not _private_field(name)}
    return public


def public_runtime_configuration(config):
    """An administrative view, not a replacement for signed snapshot bytes."""
    if config is None:
        return None
    public = deepcopy(config)
    tools = public.get('tools')
    snapshots = tools.get('snapshots') if isinstance(tools, dict) else None
    for snapshot in snapshots if isinstance(snapshots, list) else []:
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get('config'), dict):
            continue
        original = snapshot['config']
        projected = public_tool_configuration(original)
        if projected != original:
            snapshot['config'] = projected
            # Keep the source identity visible, but explicitly distinguish the
            # redacted view from canonical content carrying the original hash.
            snapshot['configuration_view'] = 'redacted_metadata'
    return public


def reject_public_oauth_material(config):
    oauth = (config or {}).get('oauth')
    if oauth is not None and not isinstance(oauth, dict):
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    if isinstance(oauth, dict) and (any(_private_field(name) for name in oauth) or oauth.get('configuration_refs')):
        # Only the OAuth owner flow may create private protocol source fields.
        raise ConfigurationError('CONFIG_BINDING_INVALID')


def merge_public_oauth_edit(current, requested):
    """Preserve opaque fields on metadata roundtrip, never silently retarget them.

    Flow start/complete/poll/disconnect use their owner repository directly and
    are not subject to this public edit contract. A normal Tool patch cannot
    inject material, change protocol identity or disconnect by omission.
    """
    current, requested = current or {}, deepcopy(requested or {})
    requested.pop('mcp_readiness', None)  # A derived read projection, not input.
    original = current.get('oauth')
    incoming = requested.get('oauth')
    private = isinstance(original, dict) and (any(_private_field(name) for name in original) or original.get('configuration_refs'))
    if not private:
        reject_public_oauth_material(requested)
        return requested
    if incoming is not None:
        if not isinstance(incoming, dict):
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        for name, value in incoming.items():
            if _private_field(name) and (name not in original or original[name] != value):
                raise ConfigurationError('CONFIG_BINDING_INVALID')
        if public_tool_configuration({'oauth': incoming}) != public_tool_configuration({'oauth': original}):
            raise ConfigurationError('CONFIG_BINDING_INVALID')
    def endpoint(config):
        return (config.get('server') or {}).get('url') or config.get('url')
    if endpoint(current) != endpoint(requested):
        raise ConfigurationError('CONFIG_DESTINATION_CHANGED')
    requested['oauth'] = deepcopy(original)
    return requested
