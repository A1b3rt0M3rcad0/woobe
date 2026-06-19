from __future__ import annotations

import re
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

API_KEY_ENVIRONMENT = "live"
API_KEY_VERSION = 1
API_KEY_PUBLIC_PREFIX_BYTES = 6
API_KEY_SECRET_BYTES = 32
API_KEY_SCOPE_RUNTIME_EXECUTE = "runtime:execute"
API_KEY_SCOPE_TRACES_READ = "traces:read"
API_KEY_SCOPE_USAGE_READ = "usage:read"
PROJECT_API_KEY_SCOPE_ORDER = (
    API_KEY_SCOPE_RUNTIME_EXECUTE,
    API_KEY_SCOPE_TRACES_READ,
    API_KEY_SCOPE_USAGE_READ,
)
PROJECT_API_KEY_SCOPES = frozenset(PROJECT_API_KEY_SCOPE_ORDER)
LEGACY_API_KEY_SCOPES = frozenset({"reading", "writing", "admin", "custom"})
PROJECT_API_KEY_ACCEPTED_SCOPES = PROJECT_API_KEY_SCOPES | LEGACY_API_KEY_SCOPES
LEGACY_API_KEY_SCOPE_MAP: dict[str, tuple[str, ...]] = {
    "reading": (API_KEY_SCOPE_TRACES_READ, API_KEY_SCOPE_USAGE_READ),
    "writing": (API_KEY_SCOPE_RUNTIME_EXECUTE,),
    "admin": PROJECT_API_KEY_SCOPE_ORDER,
}
API_KEY_PUBLIC_ID_PATTERN = re.compile(r"^[a-f0-9]{12}$")
API_KEY_PATTERN = re.compile(
    r"^rai_live_([a-f0-9]{12})_([A-Za-z0-9_-]{40,})$"
)


@dataclass(frozen=True)
class IssuedProjectApiKey:
    value: str
    public_prefix: str
    digest: bytes

    @property
    def display_prefix(self) -> str:
        return f"rai_{API_KEY_ENVIRONMENT}_{self.public_prefix}"


@dataclass(frozen=True)
class ParsedProjectApiKey:
    public_prefix: str
    secret: str

    @property
    def display_prefix(self) -> str:
        return f"rai_{API_KEY_ENVIRONMENT}_{self.public_prefix}"


def issue_project_api_key() -> IssuedProjectApiKey:
    public_prefix = secrets.token_hex(API_KEY_PUBLIC_PREFIX_BYTES)
    secret = secrets.token_urlsafe(API_KEY_SECRET_BYTES)
    value = f"rai_{API_KEY_ENVIRONMENT}_{public_prefix}_{secret}"
    return IssuedProjectApiKey(
        value=value,
        public_prefix=public_prefix,
        digest=hash_api_key(value),
    )


def parse_project_api_key(value: str) -> ParsedProjectApiKey | None:
    match = API_KEY_PATTERN.fullmatch(value)
    if match is None:
        return None
    return ParsedProjectApiKey(
        public_prefix=match.group(1),
        secret=match.group(2),
    )


def hash_api_key(value: str) -> bytes:
    return sha256(value.encode("utf-8")).digest()


def normalize_project_api_key_scopes(scopes: Sequence[str]) -> list[str]:
    requested = list(dict.fromkeys(scopes))
    if not requested:
        return [API_KEY_SCOPE_RUNTIME_EXECUTE]

    normalized: list[str] = []
    for scope in requested:
        if scope in PROJECT_API_KEY_SCOPES:
            normalized.append(scope)
            continue
        if scope == "custom":
            raise ValueError(
                "Legacy custom API key scope cannot be mapped; select explicit scopes"
            )
        mapped = LEGACY_API_KEY_SCOPE_MAP.get(scope)
        if mapped is None:
            raise ValueError(f"Unsupported API key scope: {scope}")
        normalized.extend(mapped)

    return list(dict.fromkeys(normalized))


def is_current_api_key_prefix(value: str) -> bool:
    return API_KEY_PUBLIC_ID_PATTERN.fullmatch(value) is not None


def format_api_key_prefix(value: str) -> str:
    if is_current_api_key_prefix(value):
        return f"rai_{API_KEY_ENVIRONMENT}_{value}"
    return value
