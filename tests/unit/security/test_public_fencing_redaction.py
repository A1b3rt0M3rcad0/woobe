from shared.security.redaction import REDACTED, redact_sensitive_data


def test_public_fencing_counter_survives_mcp_response_redaction():
    response = {"result": {"structuredContent": {"value": {"current_lease": {"fencing_token": 12}}}}}
    assert redact_sensitive_data(response) == response


def test_fencing_exception_does_not_disclose_token_like_credentials():
    for value in ("secret-value", True, -1, 1.5, None, {"access_token": "secret"}, ["secret"]):
        assert redact_sensitive_data({"fencing_token": value}) == {"fencing_token": REDACTED}
    for key in ("access_token", "refresh_token", "token", "password", "api_key", "authorization", "session_token"):
        assert redact_sensitive_data({key: 12}) == {key: REDACTED}


def test_secret_parent_cannot_be_bypassed_by_nested_fencing_counter():
    assert redact_sensitive_data({"access_token": {"fencing_token": 12}}) == {"access_token": REDACTED}
