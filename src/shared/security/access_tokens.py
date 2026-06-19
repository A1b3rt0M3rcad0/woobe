from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from shared.infra.errors import AuthenticationError
from shared.security.principal import AuthenticatedPrincipal


def _encode_segment(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode_segment(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Invalid authentication token") from exc


class AccessTokenCodec:
    algorithm = "HS256"

    def __init__(
        self,
        *,
        signing_key: str,
        issuer: str,
        audience: str,
        ttl_seconds: int,
        leeway_seconds: int = 30,
    ) -> None:
        if len(signing_key.encode("utf-8")) < 32:
            raise ValueError("Signing key must contain at least 32 bytes")
        if ttl_seconds <= 0:
            raise ValueError("Access token TTL must be positive")
        self._key = signing_key.encode("utf-8")
        self._issuer = issuer
        self._audience = audience
        self._ttl_seconds = ttl_seconds
        self._leeway_seconds = max(leeway_seconds, 0)

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def issue(
        self,
        *,
        user_id: UUID,
        session_id: UUID,
        now: datetime | None = None,
    ) -> str:
        issued_at = (now or datetime.now(UTC)).astimezone(UTC)
        expires_at = issued_at + timedelta(seconds=self._ttl_seconds)
        header = {"alg": self.algorithm, "typ": "JWT"}
        payload = {
            "sub": str(user_id),
            "sid": str(session_id),
            "type": "access",
            "iat": int(issued_at.timestamp()),
            "nbf": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
            "iss": self._issuer,
            "aud": self._audience,
        }
        encoded_header = _encode_segment(
            json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        encoded_payload = _encode_segment(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        signature = hmac.new(self._key, signing_input, hashlib.sha256).digest()
        return f"{encoded_header}.{encoded_payload}.{_encode_segment(signature)}"

    def decode(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> AuthenticatedPrincipal:
        parts = token.split(".")
        if len(parts) != 3:
            raise AuthenticationError("Invalid authentication token")

        encoded_header, encoded_payload, encoded_signature = parts
        try:
            header = json.loads(_decode_segment(encoded_header))
            payload: dict[str, Any] = json.loads(_decode_segment(encoded_payload))
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
            raise AuthenticationError("Invalid authentication token") from exc

        if header != {"alg": self.algorithm, "typ": "JWT"}:
            raise AuthenticationError("Invalid authentication token")

        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected_signature = hmac.new(self._key, signing_input, hashlib.sha256).digest()
        supplied_signature = _decode_segment(encoded_signature)
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise AuthenticationError("Invalid authentication token")

        required = {"sub", "sid", "type", "iat", "nbf", "exp", "iss", "aud"}
        if not required.issubset(payload):
            raise AuthenticationError("Invalid authentication token")
        if payload["type"] != "access":
            raise AuthenticationError("Invalid authentication token")
        if payload["iss"] != self._issuer or payload["aud"] != self._audience:
            raise AuthenticationError("Invalid authentication token")

        try:
            issued_timestamp = int(payload["iat"])
            not_before_timestamp = int(payload["nbf"])
            expires_timestamp = int(payload["exp"])
            user_id = UUID(str(payload["sub"]))
            session_id = UUID(str(payload["sid"]))
        except (TypeError, ValueError) as exc:
            raise AuthenticationError("Invalid authentication token") from exc

        current_timestamp = int((now or datetime.now(UTC)).timestamp())
        if issued_timestamp > current_timestamp + self._leeway_seconds:
            raise AuthenticationError("Invalid authentication token")
        if not_before_timestamp > current_timestamp + self._leeway_seconds:
            raise AuthenticationError("Authentication token is not active")
        if expires_timestamp <= current_timestamp - self._leeway_seconds:
            raise AuthenticationError("Authentication token expired")
        if expires_timestamp <= issued_timestamp:
            raise AuthenticationError("Invalid authentication token")

        return AuthenticatedPrincipal(
            user_id=user_id,
            session_id=session_id,
            issued_at=datetime.fromtimestamp(issued_timestamp, UTC),
            expires_at=datetime.fromtimestamp(expires_timestamp, UTC),
        )
