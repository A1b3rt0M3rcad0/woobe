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
            f"v{self.compatibility}.{self.feature}."
            f"{self.release_date:%Y%m%d}.{self.sequence:02d}"
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
    parsed: list[ReleaseVersion] = []
    for value in existing_versions:
        try:
            parsed.append(parse_release_version(value))
        except ValueError:
            continue

    latest = max(
        parsed,
        key=lambda item: (
            item.compatibility,
            item.feature,
            item.release_date,
            item.sequence,
        ),
        default=None,
    )
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

    sequences = [item.sequence for item in parsed if item.release_date == release_date]
    return str(
        ReleaseVersion(
            compatibility=compatibility,
            feature=feature,
            release_date=release_date,
            sequence=max(sequences, default=0) + 1,
        )
    )
