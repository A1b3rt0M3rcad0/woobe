from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from shared.infra.errors import AuthenticationError, ValidationError


def _encode_segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_segment(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Invalid ChatSurface Session token") from exc


def normalize_origin(value: str, *, allow_insecure: bool = False) -> str:
    raw = value.strip()
    parsed = urlsplit(raw)
    if (
        not parsed.scheme
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValidationError("ChatSurface origins must be exact origins")
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if "*" in hostname:
        raise ValidationError("ChatSurface origins cannot contain wildcards")
    if scheme not in {"http", "https"}:
        raise ValidationError("ChatSurface origins must use HTTP(S)")
    if scheme != "https" and not allow_insecure:
        raise ValidationError("ChatSurface origins must use HTTPS")
    default_port = 443 if scheme == "https" else 80
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("ChatSurface origin port is invalid") from exc
    display_hostname = f"[{hostname}]" if ":" in hostname else hostname
    authority = (
        display_hostname
        if port in {None, default_port}
        else f"{display_hostname}:{port}"
    )
    return f"{scheme}://{authority}"


@dataclass(frozen=True, slots=True)
class ChatSessionClaims:
    project_id: UUID
    chat_surface_id: UUID
    target_type: str
    target_id: UUID
    target_release_id: UUID
    session_id: UUID
    origin: str
    surface_credential_id: UUID
    token_epoch: int
    permissions: frozenset[str]
    issued_at: datetime
    expires_at: datetime
    jti: UUID


class ChatSessionTokenCodec:
    algorithm = "HS256"

    def __init__(
        self,
        *,
        signing_key: str,
        issuer: str,
        audience: str,
        ttl_seconds: int = 900,
        leeway_seconds: int = 30,
    ) -> None:
        if len(signing_key.encode("utf-8")) < 32:
            raise ValueError("ChatSurface signing key must contain at least 32 bytes")
        if ttl_seconds <= 0:
            raise ValueError("ChatSurface token TTL must be positive")
        self._key = signing_key.encode("utf-8")
        self._issuer = issuer
        self._audience = audience
        self._ttl_seconds = ttl_seconds
        self._leeway_seconds = max(0, leeway_seconds)

    def issue(
        self,
        *,
        project_id: UUID,
        chat_surface_id: UUID,
        target_type: str,
        target_id: UUID,
        target_release_id: UUID,
        session_id: UUID,
        origin: str,
        surface_credential_id: UUID,
        token_epoch: int,
        ttl_seconds: int | None = None,
        now: datetime | None = None,
    ) -> str:
        issued_at = (now or datetime.now(UTC)).astimezone(UTC)
        effective_ttl = ttl_seconds or self._ttl_seconds
        expires_at = issued_at + timedelta(seconds=effective_ttl)
        header = {"alg": self.algorithm, "typ": "JWT"}
        payload = {
            "type": "chat_session",
            "project_id": str(project_id),
            "chat_surface_id": str(chat_surface_id),
            "target_type": target_type,
            "target_id": str(target_id),
            "target_release_id": str(target_release_id),
            "environment": "production",
            "sid": str(session_id),
            "permissions": ["chat:history", "chat:send", "chat:stream"],
            "origin": origin,
            "surface_credential_id": str(surface_credential_id),
            "token_epoch": token_epoch,
            "jti": str(uuid4()),
            "iat": int(issued_at.timestamp()),
            "nbf": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "iss": self._issuer,
            "aud": self._audience,
        }
        encoded_header = _encode_segment(
            json.dumps(header, separators=(",", ":"), sort_keys=True).encode()
        )
        encoded_payload = _encode_segment(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = hmac.new(self._key, signing_input, hashlib.sha256).digest()
        return f"{encoded_header}.{encoded_payload}.{_encode_segment(signature)}"

    def decode(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> ChatSessionClaims:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthenticationError("Invalid ChatSurface Session token")
        encoded_header, encoded_payload, encoded_signature = parts
        try:
            header = json.loads(_decode_segment(encoded_header))
            payload: dict[str, Any] = json.loads(_decode_segment(encoded_payload))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise AuthenticationError("Invalid ChatSurface Session token") from exc
        if header != {"alg": self.algorithm, "typ": "JWT"}:
            raise AuthenticationError("Invalid ChatSurface Session token")

        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = hmac.new(self._key, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode_segment(encoded_signature)):
            raise AuthenticationError("Invalid ChatSurface Session token")

        required = {
            "type",
            "project_id",
            "chat_surface_id",
            "target_type",
            "target_id",
            "target_release_id",
            "environment",
            "sid",
            "permissions",
            "origin",
            "surface_credential_id",
            "token_epoch",
            "jti",
            "iat",
            "nbf",
            "exp",
            "iss",
            "aud",
        }
        if not required.issubset(payload):
            raise AuthenticationError("Invalid ChatSurface Session token")
        if (
            payload["type"] != "chat_session"
            or payload["environment"] != "production"
            or payload["iss"] != self._issuer
            or payload["aud"] != self._audience
            or payload["target_type"] not in {"agent", "network"}
        ):
            raise AuthenticationError("Invalid ChatSurface Session token")
        try:
            issued_timestamp = int(payload["iat"])
            not_before_timestamp = int(payload["nbf"])
            expires_timestamp = int(payload["exp"])
            claims = ChatSessionClaims(
                project_id=UUID(str(payload["project_id"])),
                chat_surface_id=UUID(str(payload["chat_surface_id"])),
                target_type=str(payload["target_type"]),
                target_id=UUID(str(payload["target_id"])),
                target_release_id=UUID(str(payload["target_release_id"])),
                session_id=UUID(str(payload["sid"])),
                origin=str(payload["origin"]),
                surface_credential_id=UUID(str(payload["surface_credential_id"])),
                token_epoch=int(payload["token_epoch"]),
                permissions=frozenset(str(item) for item in payload["permissions"]),
                issued_at=datetime.fromtimestamp(issued_timestamp, UTC),
                expires_at=datetime.fromtimestamp(expires_timestamp, UTC),
                jti=UUID(str(payload["jti"])),
            )
        except (TypeError, ValueError) as exc:
            raise AuthenticationError("Invalid ChatSurface Session token") from exc

        current_timestamp = int((now or datetime.now(UTC)).timestamp())
        if issued_timestamp > current_timestamp + self._leeway_seconds:
            raise AuthenticationError("Invalid ChatSurface Session token")
        if not_before_timestamp > current_timestamp + self._leeway_seconds:
            raise AuthenticationError("ChatSurface Session token is not active")
        if expires_timestamp <= current_timestamp - self._leeway_seconds:
            raise AuthenticationError("ChatSurface Session token expired")
        if expires_timestamp <= issued_timestamp:
            raise AuthenticationError("Invalid ChatSurface Session token")
        return claims
