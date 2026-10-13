from types import SimpleNamespace
from uuid import uuid4
import pytest
from modules.agent.application.legacy_tool_configuration import bind_legacy_tool_headers
from shared.contracts.project_configuration import ConfigurationError


def reference():
    return {"source":"legacy_configuration", "key":"SHARED", "alias_id":str(uuid4())}


def test_compiler_preserves_frozen_author_definition_and_unmigrated_fields():
    source = SimpleNamespace(config={"headers":[{"key":"Authorization", "value":"{{secret:shared}}"},
        {"key":"X-Other", "value":"{{secret:other}}"}, {"key":"Accept", "value":"application/json"}]})
    ref = reference()
    result = bind_legacy_tool_headers(source, {"shared":ref})
    assert len(source.config["headers"]) == 3 and "authentication" not in source.config
    assert result.config["authentication"] == {"type":"headers", "fields":{"Authorization":ref}}
    assert result.config["headers"] == source.config["headers"][1:]


@pytest.mark.parametrize("config", [
    {"headers":[{"key":"Host", "value":"{{secret:shared}}"}]},
    {"routes":[{"headers":[{"key":"Authorization", "value":"{{secret:shared}}"}]}]},
    {"authentication":{"type":"bearer", "fields":{"token":{"source":"project_environment", "key":"TOKEN"}}},
     "headers":[{"key":"Authorization", "value":"{{secret:shared}}"}]},
])
def test_compiler_does_not_broaden_route_or_transport_authority(config):
    with pytest.raises(ConfigurationError):
        bind_legacy_tool_headers(SimpleNamespace(config=config), {"shared":reference()})


def test_unrelated_migrated_secret_does_not_rewrite_an_existing_bearer_tool():
    source = SimpleNamespace(config={"authentication":{"type":"bearer", "fields":{"token":{"source":"project_environment", "key":"TOKEN"}}}})
    assert bind_legacy_tool_headers(source, {"shared":reference()}) is source
