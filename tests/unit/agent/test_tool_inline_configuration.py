from copy import deepcopy

import pytest

from modules.agent.domain.tool_inline_configuration import extract_inline_tool_headers
from shared.contracts.project_configuration import ConfigurationError


def test_extracts_only_global_explicit_material_and_preserves_author_input():
    source = {'headers': [{'key': 'Authorization', 'value': 'Bearer local-test-material'},
        {'key': 'X-Custom', 'value': 'custom-test-material', 'sensitive': True},
        {'key': 'Accept', 'value': 'application/json'},
        {'key': 'X-Ref', 'value': '{{secret:existing}}', 'sensitive': True}],
        'auth': {'type': 'bearer'},
        'routes': [{'headers': [{'key': 'Authorization', 'value': 'route-only-material'}]}]}
    original = deepcopy(source)
    result, material = extract_inline_tool_headers(source)
    assert source == original
    assert material == {'authorization': 'Bearer local-test-material', 'x-custom': 'custom-test-material'}
    assert result['headers'] == source['headers'][2:]
    assert result['routes'] == source['routes'] and 'auth' not in result


@pytest.mark.parametrize('extra', [
    {'authentication': {'type': 'none', 'fields': {}}},
    {'oauth': {'status': 'connected'}},
    {'server_headers': [{'key': 'authorization', 'value': 'different'}]},
])
def test_rejects_ambiguous_authorities_without_including_material(extra):
    with pytest.raises(ConfigurationError) as error:
        extract_inline_tool_headers({'headers': [{'key': 'Authorization', 'value': 'private-test-material'}], **extra})
    assert 'private-test-material' not in str(error.value)


def test_mcp_headers_are_removed_from_the_actual_server_definition():
    result, material = extract_inline_tool_headers({'server': {'url': 'https://mcp.example',
        'headers': [{'key': 'X-Api-Key', 'value': 'mcp-test-material'}]}})
    assert result['server']['headers'] == []
    assert material == {'x-api-key': 'mcp-test-material'}
