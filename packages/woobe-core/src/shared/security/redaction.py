from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

REDACTED = "[REDACTED]"
SENSITIVE_KEYS = {
    "authorization",
    "proxy-authorization",
    "api-key",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "client_secret",
    "password",
    "provider_key",
    "provider_api_key",
    "x-api-key",
}
SENSITIVE_KEY_FRAGMENTS = ("secret", "token", "password", "authorization", "api_key")
BEARER_PATTERN = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+\-/=]+")
PROJECT_API_KEY_PATTERN = re.compile(
    r"\b(?:rai_live_|woobe_(?:project|staging|production)_)[a-f0-9]{12}_[A-Za-z0-9_-]{40,}\b"
)
COMMON_PROVIDER_KEY_PATTERN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b"
)
LOG_URL_PATTERN = re.compile(r'https?://[^\s"<>]+')
SENSITIVE_OAUTH_URL_KEYS = {'state', 'code', 'device_code', 'user_code', 'code_verifier', 'code_challenge'}


def is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(
        fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS
    )


def redact_text(value: str) -> str:
    redacted = BEARER_PATTERN.sub(f"Bearer {REDACTED}", value)
    redacted = PROJECT_API_KEY_PATTERN.sub(REDACTED, redacted)
    return COMMON_PROVIDER_KEY_PATTERN.sub(REDACTED, redacted)


def redact_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return redact_text(value)
    if not parts.scheme or not parts.netloc:
        return redact_text(value)
    query = []
    for key, item in parse_qsl(parts.query, keep_blank_values=True):
        query.append((key, REDACTED if is_sensitive_key(key) or key.lower() in SENSITIVE_OAUTH_URL_KEYS else redact_text(item)))
    hostname = parts.hostname or ""
    try:
        if parts.port is not None:
            hostname = f"{hostname}:{parts.port}"
    except ValueError:
        return '[REDACTED URL]'
    return urlunsplit((parts.scheme, hostname, parts.path, urlencode(query), ""))


def redact_sensitive_data(value: Any, *, key: str | None = None) -> Any:
    if key is not None and is_sensitive_key(key):
        return REDACTED
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_sensitive_data(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_sensitive_data(item) for item in value]
    return value


class SensitiveDataLoggingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            if isinstance(record.args, Mapping):
                record.args = redact_sensitive_data(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_sensitive_data(item) for item in record.args)
        # Format URL objects too: httpx supplies a URL instance as a log argument.
        # Redacting only string arguments leaves OAuth query parameters visible.
        record.msg = LOG_URL_PATTERN.sub(lambda match: redact_url(match.group()), redact_text(record.getMessage()))
        record.args = ()
        return True
