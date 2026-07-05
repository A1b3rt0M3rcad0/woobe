from __future__ import annotations

from uuid import UUID

from modules.agent.domain.enums import KnowledgeVersionStatus
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from shared.infra.errors import ValidationError


class KnowledgeReleaseValidator:
    def __init__(self, knowledge_version_repo, vector_snapshot_repo) -> None:
        self._knowledge_version_repo = knowledge_version_repo
        self._vector_snapshot_repo = vector_snapshot_repo

    async def validate(self, release) -> None:
        if release.knowledge_version_id is None:
            return

        knowledge = await self._knowledge_version_repo.get_by_id(release.knowledge_version_id)
        if knowledge is None:
            raise ValidationError("Release KnowledgeVersion was not found")
        if knowledge.project_id != release.project_id:
            raise ValidationError("Release KnowledgeVersion belongs to another Project")
        if knowledge.agent_id != release.agent_id:
            raise ValidationError("Release KnowledgeVersion belongs to another Agent")
        if getattr(knowledge.status, "value", knowledge.status) == KnowledgeVersionStatus.ARCHIVED.value:
            raise ValidationError("Archived KnowledgeVersion cannot be used by a release")

        metadata = dict(knowledge.snapshot_metadata or {})
        vector_snapshot_id = metadata.get("vector_snapshot_id")
        if not vector_snapshot_id:
            raise ValidationError("Release KnowledgeVersion has no vector snapshot")
        try:
            snapshot_id = vector_snapshot_id if isinstance(vector_snapshot_id, UUID) else UUID(str(vector_snapshot_id))
        except (TypeError, ValueError) as exc:
            raise ValidationError("Release KnowledgeVersion has an invalid vector snapshot id") from exc

        snapshot = await self._vector_snapshot_repo.get_by_id(snapshot_id)
        if snapshot is None:
            raise ValidationError("Release vector snapshot was not found")
        if snapshot.project_id != release.project_id:
            raise ValidationError("Release vector snapshot belongs to another Project")
        if snapshot.status != VECTOR_SNAPSHOT_READY:
            raise ValidationError("Release requires a READY vector snapshot")
        if not snapshot.snapshot_hash:
            raise ValidationError("Release vector snapshot has no immutable hash")
