import base64
import json
from uuid import uuid4

import pytest

from shared.contracts.configuration_cursor import decode_configuration_cursor, encode_configuration_cursor
from shared.contracts.project_configuration import ConfigurationError


def test_cursor_keeps_independent_owner_positions_and_exact_project_environment():
    project, agent, network = uuid4(), uuid4(), uuid4()
    encoded = encode_configuration_cursor(project_id=project, environment='staging', agent=agent, network=network)
    assert decode_configuration_cursor(encoded, project_id=project, environment='staging') == {'agent': agent, 'network': network}
    for scope in ({'project_id': uuid4(), 'environment': 'staging'}, {'project_id': project, 'environment': 'production'}):
        with pytest.raises(ConfigurationError):
            decode_configuration_cursor(encoded, **scope)


@pytest.mark.parametrize('mutation', ['type', 'extra', 'version', 'uuid', 'material', 'raw'])
def test_cursor_rejects_ambiguous_unbounded_or_material_inputs(mutation):
    project = uuid4()
    body = {'v': 1, 'project': str(project), 'environment': 'draft', 'agent': None, 'network': None}
    if mutation == 'type': body['agent'] = 12
    elif mutation == 'extra': body['value'] = 'private-canary'
    elif mutation == 'version': body['v'] = True
    elif mutation == 'uuid': body['network'] = 'invalid'
    elif mutation == 'material': body['agent'] = 'private-canary'
    cursor = 'private-canary' if mutation == 'raw' else base64.urlsafe_b64encode(json.dumps(body).encode()).decode()
    with pytest.raises(ConfigurationError) as error:
        decode_configuration_cursor(cursor, project_id=project, environment='draft')
    assert 'private-canary' not in str(error.value)
