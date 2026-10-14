"""Closed read-only Project inventory cursor, never credential authority."""
import base64
import json
from uuid import UUID

from shared.contracts.project_configuration import ConfigurationError


def decode_configuration_cursor(cursor, *, project_id, environment):
    if cursor is None:
        return {'agent': None, 'network': None}
    try:
        if not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024:
            raise ValueError
        raw = base64.b64decode(cursor, altchars=b'-_', validate=True)
        document = json.loads(raw)
        if (set(document) != {'v', 'project', 'environment', 'agent', 'network'} or
                document['v'] != 1 or isinstance(document['v'], bool) or
                document['project'] != str(project_id) or document['environment'] != environment):
            raise ValueError
        if any(document[kind] is not None and not isinstance(document[kind], str) for kind in ('agent', 'network')):
            raise ValueError
        return {kind: UUID(document[kind]) if document[kind] is not None else None for kind in ('agent', 'network')}
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ConfigurationError('CONFIG_DEFINITION_INVALID') from None


def encode_configuration_cursor(*, project_id, environment, agent, network):
    document = {'v': 1, 'project': str(project_id), 'environment': environment,
                'agent': str(agent) if agent else None, 'network': str(network) if network else None}
    return base64.urlsafe_b64encode(json.dumps(document, sort_keys=True, separators=(',', ':')).encode()).decode()
