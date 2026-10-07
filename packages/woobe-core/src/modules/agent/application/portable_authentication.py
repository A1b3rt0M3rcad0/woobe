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
    try:
        url = urlsplit(value)
    except ValueError as exc:
        raise ValidationError("Portable Tool URL is invalid") from exc
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


_MODEL_AUTH_KEY = re.compile(
    r"^(?:authorization|cookie|api[-_]?key|access[-_]?token|refresh[-_]?token|password|encrypted[-_]?secret|client[-_]?secret|secret)$",
    re.IGNORECASE,
)


def validate_portable_model_authentication(specification, *, base_url=None):
    """Reject connection authentication inside an otherwise complete ModelSpec.

    Refusing export preserves the frozen identity; removing arbitrary metadata
    would change the ModelSpec hash and hide an incomplete portable definition.
    """
    _validate_url(base_url)

    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if _MODEL_AUTH_KEY.fullmatch(str(key)) and item not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    raise ValidationError(
                        "Portable Model authentication must use destination credentials"
                    )
                if str(key).lower() in {
                    "url",
                    "base_url",
                    "server_url",
                    "provider_url",
                } and isinstance(item, str):
                    _validate_url(item)
                visit(item)
            label = value.get("key") or value.get("name")
            if (
                isinstance(label, str)
                and _MODEL_AUTH_KEY.fullmatch(label)
                and value.get("value")
            ):
                raise ValidationError(
                    "Portable Model authentication must use destination credentials"
                )
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(specification)
