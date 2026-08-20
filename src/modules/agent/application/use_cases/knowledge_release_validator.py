from __future__ import annotations

from typing import Protocol, cast
from uuid import UUID

from modules.agent.application.interfaces.file_storage import FileStorage
from modules.agent.application.interfaces.repositories import (
    DocumentChunkRepository,
    DocumentRepository,
    KnowledgeVersionRepository,
)
from modules.agent.application.interfaces.vector_snapshot_repository import (
    VectorSnapshotRepository,
)
from modules.agent.application.use_cases.knowledge_use_cases import (
    DeleteDocumentUseCase as BaseDeleteDocumentUseCase,
)
from modules.agent.domain.enums import KnowledgeVersionStatus
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from shared.contracts.errors import ConflictError, ValidationError


class ActiveVectorBuildGuard(Protocol):
    async def has_active_vector_build(
        self,
        project_id: UUID,
        collection_id: UUID,
    ) -> bool: ...


class KnowledgeReleaseValidator:
    def __init__(
        self,
        knowledge_version_repo: KnowledgeVersionRepository,
        vector_snapshot_repo: VectorSnapshotRepository,
    ) -> None:
        self._knowledge_version_repo = knowledge_version_repo
        self._vector_snapshot_repo = vector_snapshot_repo

    async def validate(self, release) -> None:
        if release.knowledge_version_id is None:
            return

        knowledge = await self._knowledge_version_repo.get_by_id(
            release.knowledge_version_id
        )
        if knowledge is None:
            raise ValidationError("Release KnowledgeVersion was not found")
        if knowledge.project_id != release.project_id:
            raise ValidationError("Release KnowledgeVersion belongs to another Project")
        if knowledge.agent_id != release.agent_id:
            raise ValidationError("Release KnowledgeVersion belongs to another Agent")
        if (
            getattr(knowledge.status, "value", knowledge.status)
            == KnowledgeVersionStatus.ARCHIVED.value
        ):
            raise ValidationError("Archived KnowledgeVersion cannot be used by a release")

        metadata = dict(knowledge.snapshot_metadata or {})
        vector_snapshot_id = metadata.get("vector_snapshot_id")
        if not vector_snapshot_id:
            raise ValidationError("Release KnowledgeVersion has no vector snapshot")
        try:
            snapshot_id = (
                vector_snapshot_id
                if isinstance(vector_snapshot_id, UUID)
                else UUID(str(vector_snapshot_id))
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Release KnowledgeVersion has an invalid vector snapshot id"
            ) from exc

        snapshot = await self._vector_snapshot_repo.get_by_id(snapshot_id)
        if snapshot is None:
            raise ValidationError("Release vector snapshot was not found")
        if snapshot.project_id != release.project_id:
            raise ValidationError("Release vector snapshot belongs to another Project")
        if snapshot.status != VECTOR_SNAPSHOT_READY:
            raise ValidationError("Release requires a READY vector snapshot")
        if not snapshot.snapshot_hash:
            raise ValidationError("Release vector snapshot has no immutable hash")


class SafeDeleteDocumentUseCase(BaseDeleteDocumentUseCase):
    def __init__(
        self,
        doc_repo: DocumentRepository,
        chunk_repo: DocumentChunkRepository,
        storage: FileStorage,
    ) -> None:
        super().__init__(doc_repo, chunk_repo, storage)
        self._build_guard = cast(ActiveVectorBuildGuard, doc_repo)

    async def execute(self, document_id) -> None:
        document = await self._doc_repo.get_by_id(document_id)
        if await self._build_guard.has_active_vector_build(
            document.project_id,
            document.collection_id,
        ):
            raise ConflictError(
                "Document cannot be deleted while a vector snapshot is building"
            )
        await super().execute(document_id)
