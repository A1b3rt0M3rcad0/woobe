"""Standardized event versioning policy.

Defines append-only event evolution rules and version compatibility contracts
applicable to all modules.

Rules:
 1. Events are append-only: do not alter payload semantics without
    incrementing the version number.
 2. Consumers must declare accepted versions explicitly.
 3. An old version may only be removed after a deprecation window
    registered in runtime.
 4. Version in event_type suffix must match event_version field.
 5. Mismatched or unsupported versions trigger incompatibility rejection.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone


DEFAULT_DEPRECATION_WINDOW_DAYS: int = 90


class VersionCompatibility(str, enum.Enum):
    COMPATIBLE = "compatible"
    BACKWARD_COMPATIBLE = "backward_compatible"
    FORWARD_COMPATIBLE = "forward_compatible"
    INCOMPATIBLE = "incompatible"
    DEPRECATED = "deprecated"


ACTIVE_COMPATIBILITY_STATUSES: frozenset[str] = frozenset(
    [
        VersionCompatibility.COMPATIBLE.value,
        VersionCompatibility.BACKWARD_COMPATIBLE.value,
        VersionCompatibility.FORWARD_COMPATIBLE.value,
    ]
)

TERMINAL_COMPATIBILITY_STATUSES: frozenset[str] = frozenset(
    [
        VersionCompatibility.INCOMPATIBLE.value,
        VersionCompatibility.DEPRECATED.value,
    ]
)


class VersioningError(ValueError):
    pass


@dataclass
class VersionDeclaration:
    producer_module: str
    event_name: str
    version: int
    accepted_versions: frozenset[int]
    deprecated_at: datetime | None = None

    def __post_init__(self):
        if not self.producer_module:
            raise VersioningError("producer_module must not be empty")
        if not self.event_name:
            raise VersioningError("event_name must not be empty")
        if self.version < 1:
            raise VersioningError(f"version must be >= 1, got: {self.version}")
        if self.version not in self.accepted_versions:
            raise VersioningError(
                f"current version ({self.version}) must be in "
                f"accepted_versions ({sorted(self.accepted_versions)})"
            )
        for v in self.accepted_versions:
            if v < 1:
                raise VersioningError(
                    f"accepted_versions must all be >= 1, got: {v}"
                )

    @property
    def event_type(self) -> str:
        return f"{self.producer_module}.{self.event_name}.v{self.version}"

    @property
    def event_type_base(self) -> str:
        return f"{self.producer_module}.{self.event_name}"


def compute_event_type(producer_module: str, event_name: str, version: int) -> str:
    if not producer_module or not isinstance(producer_module, str):
        raise VersioningError("producer_module must be a non-empty string")
    if not event_name or not isinstance(event_name, str):
        raise VersioningError("event_name must be a non-empty string")
    if version < 1:
        raise VersioningError(f"version must be >= 1, got: {version}")
    return f"{producer_module}.{event_name}.v{version}"


def extract_version_from_event_type(event_type: str) -> int:
    if not event_type or not isinstance(event_type, str):
        raise VersioningError("event_type must be a non-empty string")
    segments = event_type.split(".")
    if len(segments) < 2:
        raise VersioningError(
            f"event_type must have at least 2 segments, got: {event_type!r}"
        )
    version_segment = segments[-1]
    if not version_segment.startswith("v"):
        raise VersioningError(
            f"event_type version segment must start with 'v', got: {version_segment!r}"
        )
    try:
        version = int(version_segment[1:])
    except ValueError:
        raise VersioningError(
            f"cannot parse version from event_type: {event_type!r}"
        )
    if version < 1:
        raise VersioningError(
            f"version must be >= 1, got: {version} from '{event_type}'"
        )
    return version


def extract_event_type_base(event_type: str) -> str:
    segments = event_type.split(".")
    version_segment = segments[-1]
    if not version_segment.startswith("v"):
        raise VersioningError(
            f"event_type version segment must start with 'v', got: {version_segment!r}"
        )
    return ".".join(segments[:-1])


def check_version_compatibility(
    producer_version: int,
    consumer_accepted_versions: frozenset[int],
    producer_deprecated_at: datetime | None = None,
) -> VersionCompatibility:
    if producer_version in consumer_accepted_versions:
        if producer_deprecated_at is not None:
            if producer_deprecated_at <= datetime.now(timezone.utc):
                return VersionCompatibility.DEPRECATED
        return VersionCompatibility.COMPATIBLE

    for accepted in consumer_accepted_versions:
        if accepted > producer_version:
            return VersionCompatibility.FORWARD_COMPATIBLE

    if producer_version > max(consumer_accepted_versions, default=0):
        return VersionCompatibility.BACKWARD_COMPATIBLE

    return VersionCompatibility.INCOMPATIBLE


def is_compatible(
    producer_version: int,
    consumer_accepted_versions: frozenset[int],
    producer_deprecated_at: datetime | None = None,
) -> bool:
    compat = check_version_compatibility(
        producer_version=producer_version,
        consumer_accepted_versions=consumer_accepted_versions,
        producer_deprecated_at=producer_deprecated_at,
    )
    return compat in (
        VersionCompatibility.COMPATIBLE,
        VersionCompatibility.BACKWARD_COMPATIBLE,
        VersionCompatibility.FORWARD_COMPATIBLE,
    )


def must_reject(
    producer_version: int,
    consumer_accepted_versions: frozenset[int],
    producer_deprecated_at: datetime | None = None,
) -> bool:
    compat = check_version_compatibility(
        producer_version=producer_version,
        consumer_accepted_versions=consumer_accepted_versions,
        producer_deprecated_at=producer_deprecated_at,
    )
    return compat in (
        VersionCompatibility.INCOMPATIBLE,
        VersionCompatibility.DEPRECATED,
    )


def validate_version_consistency(event_type: str, event_version: int) -> None:
    extracted = extract_version_from_event_type(event_type)
    if extracted != event_version:
        raise VersioningError(
            f"version mismatch: event_type suffix 'v{extracted}' "
            f"does not match event_version {event_version}"
        )


def validate_version_declaration(declaration: VersionDeclaration) -> None:
    if not declaration.producer_module:
        raise VersioningError("producer_module must not be empty")
    if not declaration.event_name:
        raise VersioningError("event_name must not be empty")
    if declaration.version < 1:
        raise VersioningError(f"version must be >= 1, got: {declaration.version}")
    if declaration.version not in declaration.accepted_versions:
        raise VersioningError(
            f"current version ({declaration.version}) must be in "
            f"accepted_versions ({sorted(declaration.accepted_versions)})"
        )
    for v in declaration.accepted_versions:
        if v < 1:
            raise VersioningError(
                f"accepted_versions must all be >= 1, got: {v}"
            )
