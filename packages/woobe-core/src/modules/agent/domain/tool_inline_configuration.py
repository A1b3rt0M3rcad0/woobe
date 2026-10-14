"""Recognize explicit legacy header material without guessing ordinary headers."""
from copy import deepcopy

from shared.contracts.project_configuration import ConfigurationError


SENSITIVE_HEADERS = frozenset({'authorization', 'proxy-authorization', 'x-api-key', 'api-key'})


def extract_inline_tool_headers(config):
    """Return a detached definition and private material for global headers.

    Route-local credentials are deliberately not promoted to Tool-wide authority.
    The caller must never expose the second return value in diagnostics or events.
    """
    result = deepcopy(config or {})
    material = {}
    for owner, field in ((result, 'headers'), (result, 'server_headers'), (result.get('server') or {}, 'headers')):
        if field not in owner:
            continue
        rows = owner[field]
        if not isinstance(rows, list):
            raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
        kept = []
        for row in rows:
            if not isinstance(row, dict):
                raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
            name, value = row.get('key', ''), row.get('value', '')
            sensitive = row.get('sensitive') is True or str(name).lower() in SENSITIVE_HEADERS
            if not sensitive or not value or row.get('mode') == 'remove':
                kept.append(row)
                continue
            if not isinstance(value, str):
                raise ConfigurationError('CONFIG_VALUE_INVALID')
            if '{{' in value or '}}' in value:
                # Existing Secret-template projection owns this case. Never
                # turn a template into literal credential material.
                kept.append(row)
                continue
            if not isinstance(name, str) or any(char in value for char in '\r\n\x00'):
                raise ConfigurationError('CONFIG_VALUE_INVALID')
            canonical = name.lower()
            if canonical in material:
                raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
            material[canonical] = value
        owner[field] = kept
    if material:
        if result.get('authentication') is not None or result.get('oauth'):
            raise ConfigurationError('CONFIG_BINDING_INVALID')
        # Old auth is a display hint; the actual header value is the authority.
        result.pop('auth', None)
    return result, material
