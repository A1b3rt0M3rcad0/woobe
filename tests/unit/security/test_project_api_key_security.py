from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.core.presentation.schemas import CreatedApiKeyResponse
from shared.infra.errors import RateLimitError
from shared.security.api_keys import (
    API_KEY_SCOPE_RUNTIME_EXECUTE,
    API_KEY_SCOPE_TRACES_READ,
    API_KEY_SCOPE_USAGE_READ,
    API_KEY_VERSION,
    LEGACY_API_KEY_VERSION,
    hash_api_key,
    issue_project_api_key,
    issue_runtime_api_key,
    normalize_project_api_key_scopes,
    parse_project_api_key,
)
from shared.security.rate_limit import ApiKeyConcurrencyLimiter, ApiKeyRequestLimiter
from shared.security.redaction import REDACTED, redact_sensitive_data, redact_text, redact_url


class _FakeResult:
    def __init__(self, *, one=None, scalar=None) -> None:
        self._one = one
        self._scalar = scalar

    def one(self):
        return self._one

    def scalar_one(self):
        return self._scalar


class _FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class _FakeRateLimitSession:
    def __init__(self, factory) -> None:
        self._factory = factory

    def begin(self):
        return _FakeTransaction()

    async def execute(self, statement, params):
        sql = " ".join(str(statement).split())
        if "pg_advisory_xact_lock" in sql:
            return _FakeResult()
        if "DELETE FROM core.security_rate_limit_events" in sql:
            self._factory.events = [
                event
                for event in self._factory.events
                if not (
                    event["namespace"] == params["namespace"]
                    and event["subject_key"] == params["subject_key"]
                    and event["occurred_at"] <= params["cutoff"]
                )
            ]
            return _FakeResult()
        if "SELECT COUNT(*) AS event_count" in sql:
            matches = [
                event
                for event in self._factory.events
                if event["namespace"] == params["namespace"]
                and event["subject_key"] == params["subject_key"]
                and event["occurred_at"] > params["cutoff"]
            ]
            oldest = min((event["occurred_at"] for event in matches), default=None)
            return _FakeResult(one=SimpleNamespace(event_count=len(matches), oldest_event=oldest))
        if "INSERT INTO core.security_rate_limit_events" in sql:
            self._factory.events.append(dict(params))
            return _FakeResult()
        if "DELETE FROM core.security_concurrency_leases" in sql and "expires_at <=" in sql:
            self._factory.leases = {
                lease_id: lease
                for lease_id, lease in self._factory.leases.items()
                if not (
                    lease["namespace"] == params["namespace"]
                    and lease["subject_key"] == params["subject_key"]
                    and lease["expires_at"] <= params["now"]
                )
            }
            return _FakeResult()
        if "SELECT COUNT(*) FROM core.security_concurrency_leases" in sql:
            count = sum(
                1
                for lease in self._factory.leases.values()
                if lease["namespace"] == params["namespace"]
                and lease["subject_key"] == params["subject_key"]
                and lease["expires_at"] > params["now"]
            )
            return _FakeResult(scalar=count)
        if "INSERT INTO core.security_concurrency_leases" in sql:
            self._factory.leases[params["id"]] = dict(params)
            return _FakeResult()
        if "DELETE FROM core.security_concurrency_leases" in sql and "WHERE id" in sql:
            self._factory.leases.pop(params["lease_id"], None)
            return _FakeResult()
        raise AssertionError(f"Unexpected SQL in fake rate-limit session: {sql}")


class _FakeRateLimitSessionContext:
    def __init__(self, factory) -> None:
        self._factory = factory

    async def __aenter__(self):
        return _FakeRateLimitSession(self._factory)

    async def __aexit__(self, exc_type, exc, traceback):
        return None


class _FakeRateLimitSessionFactory:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.leases: dict = {}

    def __call__(self):
        return _FakeRateLimitSessionContext(self)


def test_issued_project_api_key_has_parseable_woobe_prefix_and_digest() -> None:
    issued = issue_project_api_key()

    parsed = parse_project_api_key(issued.value)

    assert parsed is not None
    assert issued.value.startswith("woobe_project_")
    assert issued.key_version == API_KEY_VERSION
    assert parsed.key_version == API_KEY_VERSION
    assert parsed.kind == "project"
    assert parsed.environment is None
    assert parsed.public_prefix == issued.public_prefix
    assert parsed.display_prefix == issued.display_prefix
    assert hash_api_key(issued.value) == issued.digest
    assert len(issued.digest) == 32


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_issued_runtime_api_key_exposes_environment(environment: str) -> None:
    issued = issue_runtime_api_key(environment)

    parsed = parse_project_api_key(issued.value)

    assert parsed is not None
    assert issued.value.startswith(f"woobe_{environment}_")
    assert parsed.kind == "runtime"
    assert parsed.environment == environment
    assert parsed.matches_binding(kind="runtime", environment=environment)
    assert not parsed.matches_binding(
        kind="runtime",
        environment="production" if environment == "staging" else "staging",
    )


def test_legacy_project_api_key_format_remains_parseable() -> None:
    value = f"rai_live_{'a' * 12}_{'b' * 43}"

    parsed = parse_project_api_key(value)

    assert parsed is not None
    assert parsed.key_version == LEGACY_API_KEY_VERSION
    assert parsed.kind is None
    assert parsed.environment is None
    assert parsed.display_prefix == f"rai_live_{'a' * 12}"
    assert parsed.matches_binding(kind="runtime", environment="production")


def test_project_api_key_parser_rejects_malformed_values() -> None:
    assert parse_project_api_key("rai_live_short_secret") is None
    assert parse_project_api_key("woobe_development_aaaaaaaaaaaa_not-long-enough") is None
    assert parse_project_api_key("sk-not-a-project-key") is None


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (["writing"], [API_KEY_SCOPE_RUNTIME_EXECUTE]),
        (["reading"], [API_KEY_SCOPE_TRACES_READ, API_KEY_SCOPE_USAGE_READ]),
        (
            ["admin"],
            [
                API_KEY_SCOPE_RUNTIME_EXECUTE,
                API_KEY_SCOPE_TRACES_READ,
                API_KEY_SCOPE_USAGE_READ,
            ],
        ),
        (
            [API_KEY_SCOPE_RUNTIME_EXECUTE, API_KEY_SCOPE_RUNTIME_EXECUTE],
            [API_KEY_SCOPE_RUNTIME_EXECUTE],
        ),
    ],
)
def test_project_api_key_scopes_are_normalized(
    requested: list[str],
    expected: list[str],
) -> None:
    assert normalize_project_api_key_scopes(requested) == expected


def test_project_api_key_scopes_must_be_explicit() -> None:
    with pytest.raises(ValueError, match="at least one explicit scope"):
        normalize_project_api_key_scopes([])


def test_legacy_custom_scope_requires_explicit_replacement() -> None:
    with pytest.raises(ValueError, match="cannot be mapped"):
        normalize_project_api_key_scopes(["custom"])


def test_created_api_key_response_never_contains_digest_field() -> None:
    assert "key_hash" not in CreatedApiKeyResponse.model_fields


def test_redaction_removes_project_and_runtime_credentials() -> None:
    project_key = issue_project_api_key().value
    runtime_key = issue_runtime_api_key("production").value
    provider_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
    message = (
        f"project={project_key}; runtime={runtime_key}; provider={provider_key}"
    )

    redacted = redact_text(message)

    assert project_key not in redacted
    assert runtime_key not in redacted
    assert provider_key not in redacted
    assert REDACTED in redacted


def test_redaction_removes_sensitive_nested_values_and_url_query() -> None:
    project_key = issue_project_api_key().value
    payload = {
        "headers": {"Authorization": f"Bearer {project_key}"},
        "password": "plain-text-password",
        "safe": "visible",
    }

    redacted_payload = redact_sensitive_data(payload)
    redacted_url = redact_url(
        f"https://example.com/callback?access_token={project_key}&page=1#fragment"
    )

    assert redacted_payload["headers"]["Authorization"] == REDACTED
    assert redacted_payload["password"] == REDACTED
    assert redacted_payload["safe"] == "visible"
    assert project_key not in redacted_url
    assert "page=1" in redacted_url
    assert "fragment" not in redacted_url


@pytest.mark.asyncio
async def test_api_key_request_rate_limiter_rejects_excess_request() -> None:
    session_factory = _FakeRateLimitSessionFactory()
    limiter = ApiKeyRequestLimiter(
        max_requests=1,
        window_seconds=60,
        session_factory=session_factory,
    )
    subject = f"request-{uuid4()}"

    await limiter.consume(subject)

    with pytest.raises(RateLimitError) as exc_info:
        await limiter.consume(subject)
    assert exc_info.value.retry_after >= 1


@pytest.mark.asyncio
async def test_api_key_concurrency_limiter_releases_permit() -> None:
    session_factory = _FakeRateLimitSessionFactory()
    limiter = ApiKeyConcurrencyLimiter(
        max_concurrency=1,
        session_factory=session_factory,
    )
    subject = f"concurrency-{uuid4()}"

    lease_id = await limiter.acquire(subject)
    with pytest.raises(RateLimitError):
        await limiter.acquire(subject)

    await limiter.release(lease_id)
    lease_id = await limiter.acquire(subject)
    await limiter.release(lease_id)
