from modules.evaluation.application.run_diagnostics_service import _redact


def test_run_diagnostics_redacts_secrets_but_preserves_token_usage() -> None:
    payload = {
        "authorization": "Bearer secret-token-value",
        "api_key": "sk-secret-value",
        "headers": {
            "Authorization": "Bearer another-secret",
            "Content-Type": "application/json",
        },
        "input_tokens": 120,
        "output_tokens": 45,
        "reasoning_tokens": 30,
        "error": "request failed Authorization: Bearer opaque-secret and api_key=sk-private-value",
    }

    redacted = _redact(payload)

    assert redacted["authorization"] == "<redacted>"
    assert redacted["api_key"] == "<redacted>"
    assert redacted["headers"]["Authorization"] == "<redacted>"
    assert redacted["headers"]["Content-Type"] == "application/json"
    assert redacted["input_tokens"] == 120
    assert redacted["output_tokens"] == 45
    assert redacted["reasoning_tokens"] == 30
    assert "opaque-secret" not in redacted["error"]
    assert "sk-private-value" not in redacted["error"]


def test_run_diagnostics_redacts_tokens_in_urls_and_nested_values() -> None:
    payload = {
        "request": {
            "url": "https://provider.example/v1/models?access_token=super-secret&mode=test",
            "client_secret": "hidden",
            "metadata": {"refresh_token": "hidden-too"},
        }
    }

    redacted = _redact(payload)

    assert "super-secret" not in redacted["request"]["url"]
    assert "access_token=<redacted>" in redacted["request"]["url"]
    assert redacted["request"]["client_secret"] == "<redacted>"
    assert redacted["request"]["metadata"]["refresh_token"] == "<redacted>"
