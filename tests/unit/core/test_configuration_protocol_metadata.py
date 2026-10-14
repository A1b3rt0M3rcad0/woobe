import pytest

from modules.core.domain.configuration_protocol_metadata import validate_protocol_metadata
from shared.contracts.project_configuration import ConfigurationError, ConfigurationResolvedValue
from uuid import uuid4


def test_protocol_metadata_is_closed_non_secret_and_material_repr_is_opaque():
    original = {'protocol': 'mcp_oauth', 'state': 'connected', 'token_type': 'Bearer', 'expires_at': '2026-10-14T12:00:00+00:00'}
    parsed = validate_protocol_metadata(original)
    assert parsed == original and parsed is not original
    resolved = ConfigurationResolvedValue(value='private-canary', value_version=uuid4(),
        environment='draft', source='environment', protocol_metadata=parsed)
    assert 'private-canary' not in repr(resolved)


@pytest.mark.parametrize('metadata', [
    {'protocol': 'mcp_oauth', 'access_token': 'private-canary'},
    {'protocol': 'mcp_oauth', 'state': 'private-canary'},
    {'protocol': 'mcp_oauth', 'state': []},
    {'protocol': 'mcp_oauth', 'token_type': 'private-canary'},
    {'protocol': 'mcp_oauth', 'expires_at': '2026-10-14T12:00:00'},
    {'protocol': 'mcp_oauth', 'expires_at': 'private-canary'},
    {'protocol': 'arbitrary-provider'}, ['private-canary'],
])
def test_protocol_metadata_cannot_carry_material_or_ambiguous_time(metadata):
    with pytest.raises(ConfigurationError) as rejected:
        validate_protocol_metadata(metadata)
    assert 'private-canary' not in str(rejected.value)
