import pytest

from modules.core.domain.project_configuration import canonical_destination, compile_authentication, validate_declaration, validate_material
from modules.core.infra.database.configuration_resolution import destination_matches
from shared.contracts.project_configuration import ConfigurationError


@pytest.mark.parametrize("value", [None, "", "\r\n", "secret\nheader", 0, False, [], {}])
def test_tokens_reject_invalid_input_without_echo(value):
    with pytest.raises(ConfigurationError) as error:
        validate_material(value, kind="secret", value_format="token", rules={"min_length": 0})
    assert str(error.value) == "Configuration value does not satisfy its declared format"


@pytest.mark.parametrize("value", ["0", "false", "  significant spaces  "])
def test_string_preserves_nonempty_values(value):
    validate_material(value, kind="value", value_format="string", rules={})


def test_empty_only_explicit_nonsecret():
    validate_material("", kind="value", value_format="string", rules={"allow_empty": True})
    with pytest.raises(ConfigurationError):
        validate_material("", kind="secret", value_format="string", rules={"min_length": 0})


@pytest.mark.parametrize("kind,form,rules", [([], "token", {}), ("secret", [], {}), ("secret", "token", {"allow_empty": True}),
    ("secret", "token", {"regex": ".*"}), ("secret", "token", {"max_length": True})])
def test_declaration_has_bounded_rules(kind, form, rules):
    with pytest.raises(ConfigurationError):
        validate_declaration("PROVIDER_KEY", kind, form, rules)


@pytest.mark.parametrize("auth", [{"type": []}, {"type": "api_key", "fields": {"api_key": "canary"}},
    {"type": "api_key", "fields": {"api_key": {"source": "project_environment", "key": "KEY", "environment": "production"}}},
    {"type": "api_key", "fields": {"api_key": {"source": "inline", "key": "KEY"}}}])
def test_bindings_reject_inline_and_environment_overrides(auth):
    with pytest.raises(ConfigurationError):
        compile_authentication(auth)


def test_typed_multi_field_binding_and_none():
    auth = {"type": "basic", "fields": {field: {"source": "project_environment", "key": field.upper()} for field in ("username", "password")}}
    assert compile_authentication(auth) == auth
    with pytest.raises(ConfigurationError):
        compile_authentication({"type": "none"})
    assert compile_authentication({"type": "none"}, allow_none=True)["fields"] == {}


@pytest.mark.parametrize("destination", ["https://user:secret@example.com", "https://example.com/?token=x",
    "https://example.com/a/../b", "https://example.com/a%2fb", "file:///tmp/token", "https://example.com/#secret"])
def test_destination_identity_rejects_hidden_auth_and_ambiguity(destination):
    with pytest.raises(ConfigurationError):
        canonical_destination(destination)


def test_destination_scope_is_path_and_origin_bounded():
    assert canonical_destination("HTTPS://EXAMPLE.COM:443/v1/") == "https://example.com/v1"
    assert destination_matches("https://example.com/v1", "https://example.com/v1/chat/completions")
    assert not destination_matches("https://example.com/v1", "https://example.com/v10")
    assert not destination_matches("https://example.com/v1", "https://example.com.evil/v1")
    assert not destination_matches("https://example.com/v1", "http://example.com/v1")


@pytest.mark.parametrize("field", ["Host", "Proxy-Authorization", "Transfer-Encoding", "X-Forwarded-Host"])
def test_authentication_cannot_override_routing_headers(field):
    with pytest.raises(ConfigurationError):
        compile_authentication({"type": "headers", "fields": {field: {"source": "project_environment", "key": "TOKEN"}}})


@pytest.mark.parametrize("path", ["/%252e%252e/private", "/safe%255cprivate", "/%25252fprivate", "/%00private"])
def test_destination_rejects_nested_encoded_path_escapes(path):
    with pytest.raises(ConfigurationError):
        canonical_destination("https://approved.example" + path)
