"""Typed Tool authentication references, separate from model-visible inputs."""
import hashlib
import json
from uuid import UUID
from urllib.parse import urlsplit, urlunsplit
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError, compile_authentication


def tool_authentication(config, *, allow_legacy=False):
    if not isinstance(config, dict) or config.get('authentication') is None:
        return None
    return compile_authentication(config["authentication"], allow_none=True, allow_legacy=allow_legacy)


def tool_destination(value):
    """Static scheme/authority/path boundary; rendered sends are checked again.

    Parameterized paths require approval of their containing static path. URL
    query parameters do not define credential authority. Scheme/host templates
    are never credentials destinations.
    """
    import re
    if not isinstance(value, str) or not value or any(c in value for c in '\r\n\x00\\'):
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.fragment or any(c in parsed.netloc for c in '{}%')):
            raise ValueError
        path = parsed.path
        templates = list(re.finditer(r'\{\{[A-Za-z_][A-Za-z0-9_.]*\}\}', path))
        if any(c in re.sub(r'\{\{[A-Za-z_][A-Za-z0-9_.]*\}\}', '', path) for c in '{}'):
            raise ValueError
        if templates:
            prefix = path[:templates[0].start()]
            path = prefix[:prefix.rfind('/') + 1]
        # The central owner canonicalizes this boundary and rejects traversal,
        # encoded separators and malformed ports before storing a reference.
        return urlunsplit((parsed.scheme, parsed.netloc, path or '/', '', ''))
    except (ValueError, TypeError):
        raise ConfigurationError('CONFIG_BINDING_INVALID') from None


def authentication_scopes(config, *, allow_legacy=False):
    """Authentication is scoped to the parent Tool or one concrete HTTP route."""
    scopes = []
    auth = tool_authentication(config, allow_legacy=allow_legacy)
    destination = (config.get('server') or {}).get('url') or config.get('base_url') or config.get('url')
    if auth is not None:
        scopes.append(('/config/authentication/fields/', destination, auth))
    identifiers = set()
    for route in config.get('routes', []):
        if not isinstance(route, dict) or route.get('authentication') is None:
            continue
        identifier = str(route.get('id') or '').strip()
        if not identifier or len(identifier) > 128 or identifier in identifiers or any(c in identifier for c in '\r\n\x00'):
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        identifiers.add(identifier)
        base = config.get('base_url')
        path = route.get('path')
        if not isinstance(base, str) or not isinstance(path, str) or not path:
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc:
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        destination = base.rstrip('/') + '/' + path.lstrip('/')
        # Escape the stable route ID as a JSON Pointer token, not an array index.
        token = identifier.replace('~', '~0').replace('/', '~1')
        auth = compile_authentication(route['authentication'], allow_none=True, allow_legacy=allow_legacy)
        scopes.append(('/config/routes/' + token + '/authentication/fields/', destination, auth))
    return scopes


def invocation_authentication(config, route_identifier=None):
    global_auth = tool_authentication(config, allow_legacy=True)
    if route_identifier is None:
        return global_auth
    route_identifier = str(route_identifier).strip()
    matches = [route for route in config.get('routes', []) if route_identifier in {
        str(route.get('id') or ''), str(route.get('operation_id') or '')}]
    if len(matches) > 1:
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    if not matches:
        return global_auth
    route = matches[0]
    if route.get('authentication') is None:
        return global_auth
    route_auth = compile_authentication(route['authentication'], allow_none=True, allow_legacy=True)
    if route_auth['type'] == 'none':
        return None
    token = str(route['id']).strip().replace('~', '~0').replace('/', '~1')
    # An internal transport projection. Public authentication DTOs reject this
    # composite form; it carries references and field paths, never material.
    bindings = []
    if global_auth is not None and global_auth['fields']:
        bindings.append({'authentication': global_auth, 'field_prefix': '/config/authentication/fields/'})
    if route_auth['fields']:
        bindings.append({'authentication': route_auth,
                         'field_prefix': '/config/routes/' + token + '/authentication/fields/'})
    return {'type': 'composite', 'fields': {}, 'bindings': bindings} if bindings else None


def tool_dependencies(tool, *, impact=()):
    config = tool.config or {}
    scopes = authentication_scopes(config, allow_legacy=True)
    if not scopes:
        return []
    if len(scopes) == 1 and scopes[0][0] == '/config/authentication/fields/':
        _, destination, auth = scopes[0]
        document = {'authentication': auth, 'destination': destination}
    else:
        document = {'authentication_scopes': scopes}
    revision = hashlib.sha256(json.dumps(document, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    dependencies = []
    for prefix, destination, auth in scopes:
        if not auth['fields']:
            continue
        destination = tool_destination(destination)
        dependencies.extend(ConfigurationDependency(tool.project_id, 'tool', tool.id, revision,
            prefix + field, ref['key'], destination, impact=impact,
            legacy_alias_id=UUID(ref['alias_id']) if ref['source'] == 'legacy_configuration' else None)
            for field, ref in auth['fields'].items())
    return dependencies


def validate_tool_authentication(config, *, allow_legacy=False):
    scopes = authentication_scopes(config, allow_legacy=allow_legacy)
    if not scopes:
        return
    auth = tool_authentication(config, allow_legacy=allow_legacy) or {'type': 'none', 'fields': {}}
    # Mixing two authentication authorities is ambiguous, even if one is legacy.
    hint = config.get('auth')
    no_legacy_auth = hint is None or (isinstance(hint, dict)
        and set(hint) <= {'type', 'credentials'} and hint.get('type') == 'none'
        and hint.get('credentials') in (None, []))
    if not no_legacy_auth or config.get("oauth"):
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    names = {"authorization", "proxy-authorization", "x-api-key"}
    if auth["type"] == "headers":
        names |= {name.lower() for name in auth["fields"]}
    def header_rows(raw):
        if isinstance(raw, dict):
            return [{"key": key, "value": value} for key, value in raw.items()]
        if raw is None:
            return []
        if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        return raw
    headers = [*header_rows(config.get("headers")), *header_rows(config.get("server_headers")), *header_rows((config.get("server") or {}).get("headers"))]
    if any(str(header.get("key", "")).lower() in names for header in headers):
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    # Remote references cannot be copied into prompts, bodies, schemas or URLs.
    def scan(value):
        if isinstance(value, dict):
            if value.get("source") in {'project_environment', 'legacy_configuration'}:
                raise ConfigurationError("CONFIG_BINDING_INVALID")
            for item in value.values():
                scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)
        elif isinstance(value, str):
            import re
            if re.search(r"\{\{\s*secret\s*:", value):
                raise ConfigurationError("CONFIG_BINDING_INVALID")
    for route in config.get('routes', []):
        if route.get('authentication') is not None:
            route_auth = compile_authentication(route['authentication'], allow_none=True, allow_legacy=allow_legacy)
            route_names = {'authorization', 'proxy-authorization', 'x-api-key'}
            if route_auth['type'] == 'headers':
                route_names |= {name.lower() for name in route_auth['fields']}
            if any(str(row.get('key', '')).lower() in route_names for row in header_rows(route.get('headers'))):
                raise ConfigurationError('CONFIG_BINDING_INVALID')
    visible = {key: value for key, value in config.items() if key not in {'authentication', 'routes'}}
    visible['routes'] = [{key: value for key, value in route.items() if key != 'authentication'}
                         for route in config.get('routes', [])]
    scan(visible)
