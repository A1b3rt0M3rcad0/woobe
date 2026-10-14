"""Closed, non-secret material interpretation owned by protocol writers."""
from datetime import datetime

from shared.contracts.project_configuration import ConfigurationError


def validate_protocol_metadata(metadata):
    if metadata is None:
        return {}
    if not isinstance(metadata, dict) or set(metadata) - {'protocol', 'expires_at', 'token_type', 'state'}:
        raise ConfigurationError('CONFIG_VALUE_INVALID')
    if not metadata:
        return {}
    if metadata.get('protocol') != 'mcp_oauth':
        raise ConfigurationError('CONFIG_VALUE_INVALID')
    if 'token_type' in metadata and metadata['token_type'] != 'Bearer':
        raise ConfigurationError('CONFIG_VALUE_INVALID')
    if 'state' in metadata and (not isinstance(metadata['state'], str) or metadata['state'] not in {'pending', 'device_pending', 'connected', 'disconnected'}):
        raise ConfigurationError('CONFIG_VALUE_INVALID')
    result = dict(metadata)
    if metadata.get('expires_at') is not None:
        try:
            raw = metadata['expires_at']
            if not isinstance(raw, str) or len(raw) > 64:
                raise ValueError
            expiry = datetime.fromisoformat(raw)
            if expiry.tzinfo is None:
                raise ValueError
            result['expires_at'] = expiry.isoformat()
        except (ValueError, TypeError):
            raise ConfigurationError('CONFIG_VALUE_INVALID') from None
    return result
