from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from modules.chat_surface.security import ChatSessionTokenCodec, normalize_origin
from shared.infra.errors import AuthenticationError, ValidationError


def _codec() -> ChatSessionTokenCodec:
    return ChatSessionTokenCodec(
        signing_key="chat-surface-test-signing-key-that-is-long-enough",
        issuer="projectrai-chat",
        audience="projectrai-chat-embed",
        ttl_seconds=900,
        leeway_seconds=0,
    )


def test_origin_normalization_requires_exact_https_origin() -> None:
    assert normalize_origin("https://APP.example.com:443/") == "https://app.example.com"
    with pytest.raises(ValidationError):
        normalize_origin("https://app.example.com/path")
    with pytest.raises(ValidationError):
        normalize_origin("http://app.example.com")


def test_local_http_origin_is_only_allowed_explicitly() -> None:
    with pytest.raises(ValidationError):
        normalize_origin("http://localhost:5173")
    assert (
        normalize_origin("http://localhost:5173", allow_insecure=True)
        == "http://localhost:5173"
    )
    assert (
        normalize_origin("http://[::1]:5173", allow_insecure=True)
        == "http://[::1]:5173"
    )


def test_session_token_round_trip_preserves_all_bindings() -> None:
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    project_id = uuid4()
    surface_id = uuid4()
    target_id = uuid4()
    session_id = uuid4()
    credential_id = uuid4()
    token = _codec().issue(
        project_id=project_id,
        chat_surface_id=surface_id,
        target_type="agent",
        target_id=target_id,
        session_id=session_id,
        origin="https://app.example.com",
        surface_credential_id=credential_id,
        token_epoch=4,
        now=now,
    )

    claims = _codec().decode(token, now=now + timedelta(seconds=1))

    assert claims.project_id == project_id
    assert claims.chat_surface_id == surface_id
    assert claims.target_id == target_id
    assert claims.session_id == session_id
    assert claims.surface_credential_id == credential_id
    assert claims.origin == "https://app.example.com"
    assert claims.token_epoch == 4
    assert claims.permissions == {"chat:history", "chat:send", "chat:stream"}


def test_session_token_rejects_tampering_and_expiration() -> None:
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    token = _codec().issue(
        project_id=uuid4(),
        chat_surface_id=uuid4(),
        target_type="network",
        target_id=uuid4(),
        session_id=uuid4(),
        origin="https://app.example.com",
        surface_credential_id=uuid4(),
        token_epoch=1,
        ttl_seconds=60,
        now=now,
    )
    header, payload, signature = token.split(".")

    with pytest.raises(AuthenticationError):
        _codec().decode(
            f"{header}.{payload}.{signature[:-1]}x",
            now=now + timedelta(seconds=1),
        )
    with pytest.raises(AuthenticationError):
        _codec().decode(token, now=now + timedelta(seconds=61))
