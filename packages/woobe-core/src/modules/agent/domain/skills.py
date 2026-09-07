from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

import uuid6


def skill_package_hash(package: dict[str, Any]) -> str:
    payload = json.dumps(
        package, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Skill:
    project_id: UUID
    name: str
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SkillVersion:
    skill_id: UUID
    project_id: UUID
    version: str
    package: dict[str, Any]
    package_hash: str
    id: UUID = field(default_factory=uuid6.uuid7)
    created_at: datetime | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "skill_id": str(self.skill_id),
            "skill_version_id": str(self.id),
            "project_id": str(self.project_id),
            "version": self.version,
            "package_hash": self.package_hash,
            "package": deepcopy(self.package),
        }
