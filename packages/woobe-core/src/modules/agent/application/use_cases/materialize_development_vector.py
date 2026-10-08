from modules.agent.application.interfaces.vector_snapshot_repository import (
    VectorSnapshotRepository,
)
from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.use_cases.vector_snapshot_use_cases import (
    _normalize_build_config,
    _snapshot_to_output,
)
from shared.contracts.errors import ConflictError


class MaterializeDevelopmentVector:
    def __init__(self, repository: VectorSnapshotRepository, create: UseCase):
        self._repository, self._create = repository, create

    async def execute(self, request):
        base = request.version
        for attempt in range(1000):
            version = base if attempt == 0 else base[:52] + "-retry-" + str(attempt)
            candidate = request.model_copy(update={"version": version})
            existing = await self._repository.get_by_collection_version(
                request.project_id, request.collection_id, version
            )
            if existing is None:
                return await self._create.execute(candidate)
            documents = await self._repository.list_snapshot_documents(existing.id)
            expected_config = _normalize_build_config(
                request, embedding=existing.build_config["embedding"]
            )
            if (
                existing.embedding_provider_model_id
                != request.embedding_provider_model_id
                or existing.build_config != expected_config
                or {item.document_id for item in documents}
                != set(request.document_ids or [])
                or existing.status == "ARCHIVED"
            ):
                raise ConflictError(
                    "Existing development Vector Snapshot has different content or is unavailable"
                )
            if existing.status not in {"FAILED", "CANCELLED"}:
                return _snapshot_to_output(existing)
        raise ConflictError(
            "Vector build retry budget exhausted; inspect failed snapshots"
        )
