from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from hashlib import sha256

API_KEY_ENVIRONMENT = "live"
API_KEY_PUBLIC_PREFIX_BYTES = 6
API_KEY_SECRET_BYTES = 32
API_KEY_PREFIX_PATTERN = re.compile(r"^rai_live_([a-f0-9]{12})$")
API_KEY_PATTERN = re.compile(
    r"^(rai_live_([a-f0-9]{12}))_([A-Za-z0-9_-]{40,})$"
)


@dataclass(frozen=True)
class IssuedProjectApiKey:
    value: str
    public_prefix: str
    digest: bytes


@dataclass(frozen=True)
class ParsedProjectApiKey:
    public_prefix: str
    secret: str


def issue_project_api_key() -> IssuedProjectApiKey:
    public_id = secrets.token_hex(API_KEY_PUBLIC_PREFIX_BYTES)
    public_prefix = f"rai_{API_KEY_ENVIRONMENT}_{public_id}"
    secret = secrets.token_urlsafe(API_KEY_SECRET_BYTES)
    value = f"{public_prefix}_{secret}"
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
        secret=match.group(3),
    )


def hash_api_key(value: str) -> bytes:
    return sha256(value.encode("utf-8")).digest()


def is_current_api_key_prefix(value: str) -> bool:
    return API_KEY_PREFIX_PATTERN.fullmatch(value) is not None
