from __future__ import annotations

import re
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256

LEGACY_API_KEY_ENVIRONMENT = "live"
LEGACY_API_KEY_VERSION = 1
API_KEY_VERSION = 2
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
RUNTIME_API_KEY_ENVIRONMENTS = frozenset({"staging", "production"})
API_KEY_PUBLIC_ID_PATTERN = re.compile(r"^[a-f0-9]{12}$")
LEGACY_API_KEY_PATTERN = re.compile(
    r"^rai_live_([a-f0-9]{12})_([A-Za-z0-9_-]{40,})$"
)
WOOBE_API_KEY_PATTERN = re.compile(
    r"^woobe_(project|surface|control|staging|production)_([a-f0-9]{12})_([A-Za-z0-9_-]{40,})$"
)
API_KEY_CANDIDATE_PREFIXES = ("rai_live_", "woobe_")
API_KEY_ENVIRONMENT = LEGACY_API_KEY_ENVIRONMENT
API_KEY_PATTERN = LEGACY_API_KEY_PATTERN


@dataclass(frozen=True)
class IssuedProjectApiKey:
    value: str
    public_prefix: str
    digest: bytes
    key_version: int
    kind: str
    environment: str | None = None

    @property
    def display_prefix(self) -> str:
        return format_api_key_prefix(
            self.public_prefix,
            key_version=self.key_version,
            kind=self.kind,
            environment=self.environment,
        )


@dataclass(frozen=True)
class ParsedProjectApiKey:
    public_prefix: str
    secret: str
    key_version: int
    kind: str | None = None
    environment: str | None = None

    @property
    def display_prefix(self) -> str:
        return format_api_key_prefix(
            self.public_prefix,
            key_version=self.key_version,
            kind=self.kind,
            environment=self.environment,
        )

    def matches_binding(self, *, kind: str, environment: str | None) -> bool:
        if self.key_version == LEGACY_API_KEY_VERSION:
            return True
        return self.kind == kind and self.environment == environment


def _issue_api_key(*, kind: str, environment: str | None) -> IssuedProjectApiKey:
    public_prefix = secrets.token_hex(API_KEY_PUBLIC_PREFIX_BYTES)
    secret = secrets.token_urlsafe(API_KEY_SECRET_BYTES)
    namespace = _woobe_namespace(kind=kind, environment=environment)
    value = f"woobe_{namespace}_{public_prefix}_{secret}"
    return IssuedProjectApiKey(
        value=value,
        public_prefix=public_prefix,
        digest=hash_api_key(value),
        key_version=API_KEY_VERSION,
        kind=kind,
        environment=environment,
    )


def _woobe_namespace(*, kind: str, environment: str | None) -> str:
    if kind == "project":
        if environment is not None:
            raise ValueError("Project API keys cannot be bound to an environment")
        return "project"
    if kind == "chat_surface":
        if environment is not None:
            raise ValueError("ChatSurface Access Keys cannot bind an environment")
        return "surface"
    if kind == "control":
        if environment is not None:
            raise ValueError("Control-plane API keys cannot bind an environment")
        return "control"
    if kind == "runtime" and environment in RUNTIME_API_KEY_ENVIRONMENTS:
        return str(environment)
    raise ValueError("Unsupported API key binding")


def issue_project_api_key() -> IssuedProjectApiKey:
    return _issue_api_key(kind="project", environment=None)


def issue_runtime_api_key(environment: str) -> IssuedProjectApiKey:
    return _issue_api_key(kind="runtime", environment=environment)


def issue_chat_surface_api_key() -> IssuedProjectApiKey:
    return _issue_api_key(kind="chat_surface", environment=None)


def issue_control_api_key() -> IssuedProjectApiKey:
    return _issue_api_key(kind="control", environment=None)


def parse_project_api_key(value: str) -> ParsedProjectApiKey | None:
    legacy_match = LEGACY_API_KEY_PATTERN.fullmatch(value)
    if legacy_match is not None:
        return ParsedProjectApiKey(
            public_prefix=legacy_match.group(1),
            secret=legacy_match.group(2),
            key_version=LEGACY_API_KEY_VERSION,
        )

    woobe_match = WOOBE_API_KEY_PATTERN.fullmatch(value)
    if woobe_match is None:
        return None

    namespace = woobe_match.group(1)
    if namespace == "project":
        kind = "project"
        environment = None
    elif namespace == "surface":
        kind = "chat_surface"
        environment = None
    elif namespace == "control":
        kind = "control"
        environment = None
    else:
        kind = "runtime"
        environment = namespace

    return ParsedProjectApiKey(
        public_prefix=woobe_match.group(2),
        secret=woobe_match.group(3),
        key_version=API_KEY_VERSION,
        kind=kind,
        environment=environment,
    )


def is_api_key_candidate(value: str) -> bool:
    return value.startswith(API_KEY_CANDIDATE_PREFIXES)


def hash_api_key(value: str) -> bytes:
    return sha256(value.encode("utf-8")).digest()


def normalize_project_api_key_scopes(scopes: Sequence[str]) -> list[str]:
    requested = list(dict.fromkeys(scopes))
    if not requested:
        raise ValueError("Project API keys require at least one explicit scope")

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


def format_api_key_prefix(
    value: str,
    *,
    key_version: int = API_KEY_VERSION,
    kind: str = "project",
    environment: str | None = None,
) -> str:
    if not is_current_api_key_prefix(value):
        return value
    if key_version == LEGACY_API_KEY_VERSION:
        return f"rai_{LEGACY_API_KEY_ENVIRONMENT}_{value}"
    namespace = _woobe_namespace(kind=kind, environment=environment)
    return f"woobe_{namespace}_{value}"
