"""Portable Tool author configuration carries references instead of authentication values."""

import re
from urllib.parse import parse_qsl, urlsplit
from shared.contracts.errors import ValidationError

_SENSITIVE = re.compile(
    r"authorization|cookie|api[-_]?key|access[-_]?token|password|secret", re.IGNORECASE
)
_REFERENCE = re.compile(r"\{\{\s*(?:secret:|project_env\.)[^{}]+\}\}")

_AUTH_REFERENCE = re.compile(
    r"(?:(?:Bearer|Basic)\s+)?\{\{\s*(?:secret:|project_env\.)[^{}]+\}\}", re.IGNORECASE
)


def _require_reference_headers(headers):
    for header in headers or []:
        if header.get("mode") == "remove":
            continue
        if header.get("sensitive") or _SENSITIVE.search(str(header.get("key", ""))):
            value = str(header.get("value", ""))
            if value and not _AUTH_REFERENCE.fullmatch(value.strip()):
                raise ValidationError(
                    "Portable Tool authentication must use destination references"
                )


def _validate_url(value):
    if not value:
        return
    url = urlsplit(value)
    if (
        url.username is not None
        or url.password is not None
        or any(
            _SENSITIVE.search(key)
            and content
            and not _REFERENCE.fullmatch(content.strip())
            for key, content in parse_qsl(url.query)
        )
    ):
        raise ValidationError("Portable Tool URL contains authentication material")


def validate_portable_tool_authentication(config):
    _validate_url(config.get("url"))
    _validate_url(config.get("base_url"))
    _require_reference_headers(config.get("headers"))
    _require_reference_headers(config.get("server_headers"))
    server = config.get("server") or {}
    _validate_url(server.get("url"))
    _require_reference_headers(server.get("headers"))
    for route in config.get("routes", []):
        _validate_url(route.get("path"))
        _require_reference_headers(route.get("headers"))
