from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum
import re


class ReleaseChangeKind(StrEnum):
    COMPATIBILITY = "compatibility"
    FEATURE = "feature"
    CHANGE = "change"


@dataclass(frozen=True, slots=True)
class ReleaseVersion:
    compatibility: int
    feature: int
    release_date: date
    sequence: int

    def __str__(self) -> str:
        return (
            f"v{self.compatibility}."
            f"{self.feature}."
            f"{self.release_date:%Y%m%d}."
            f"{self.sequence:02d}"
        )


_VERSION_PATTERN = re.compile(
    r"^v(?P<compatibility>\d+)\."
    r"(?P<feature>\d+)\."
    r"(?P<date>\d{8})\."
    r"(?P<sequence>\d{2,})$"
)


def parse_release_version(value: str) -> ReleaseVersion:
    match = _VERSION_PATTERN.match(value)
    if not match:
        raise ValueError(f"Invalid release version format: {value!r}")

    raw_date = match.group("date")
    return ReleaseVersion(
        compatibility=int(match.group("compatibility")),
        feature=int(match.group("feature")),
        release_date=date(
            int(raw_date[0:4]),
            int(raw_date[4:6]),
            int(raw_date[6:8]),
        ),
        sequence=int(match.group("sequence")),
    )


def calculate_next_release_version(
    existing_versions: list[str],
    change_kind: ReleaseChangeKind | str,
    *,
    now: datetime | None = None,
) -> str:
    """Calculate the next system-owned release version.

    Format: v{compatibility}.{feature}.{YYYYMMDD}.{daily_sequence}

    Rules:
    - compatibility change increments the first number and resets feature to 0;
    - feature change keeps compatibility and increments the second number;
    - regular change keeps compatibility and feature;
    - daily sequence is scoped by release date across all releases created that day;
    - invalid historical versions are ignored so legacy data does not block release.
    """

    parsed_versions = _parse_valid_versions(existing_versions)
    latest = _latest_version(parsed_versions)
    kind = ReleaseChangeKind(change_kind)
    release_date = (now or datetime.now(timezone.utc)).date()

    if latest is None:
        compatibility = 0
        feature = 0
    elif kind is ReleaseChangeKind.COMPATIBILITY:
        compatibility = latest.compatibility + 1
        feature = 0
    elif kind is ReleaseChangeKind.FEATURE:
        compatibility = latest.compatibility
        feature = latest.feature + 1
    else:
        compatibility = latest.compatibility
        feature = latest.feature

    sequence = _next_daily_sequence(
        parsed_versions,
        release_date=release_date,
    )

    return str(
        ReleaseVersion(
            compatibility=compatibility,
            feature=feature,
            release_date=release_date,
            sequence=sequence,
        )
    )


def _parse_valid_versions(values: list[str]) -> list[ReleaseVersion]:
    versions: list[ReleaseVersion] = []
    for value in values:
        try:
            versions.append(parse_release_version(value))
        except ValueError:
            continue
    return versions


def _latest_version(versions: list[ReleaseVersion]) -> ReleaseVersion | None:
    if not versions:
        return None
    return max(
        versions,
        key=lambda version: (
            version.compatibility,
            version.feature,
            version.release_date,
            version.sequence,
        ),
    )


def _next_daily_sequence(
    versions: list[ReleaseVersion],
    *,
    release_date: date,
) -> int:
    same_day = [
        version.sequence
        for version in versions
        if version.release_date == release_date
    ]
    if not same_day:
        return 1
    return max(same_day) + 1
