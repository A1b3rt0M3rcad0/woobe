from modules.agent.domain.imported_dependencies import ImportedDependencyPending
from modules.agent.domain.vector_snapshot_entities import (
    VECTOR_SNAPSHOT_BUILDING,
    VECTOR_SNAPSHOT_READY,
)
from shared.contracts.errors import ConflictError, NotFoundError


class VerifyImportedVectorUseCase:
    def __init__(self, snapshots):
        self._snapshots = snapshots

    async def execute(self, definition):
        snapshot = await self._snapshots.get_by_id(definition.snapshot_id)
        if snapshot is None or snapshot.project_id != definition.project_id:
            raise NotFoundError("Imported VectorSnapshot is unavailable")
        if snapshot.status == VECTOR_SNAPSHOT_BUILDING:
            raise ImportedDependencyPending(
                [
                    {
                        "kind": "VectorSnapshot",
                        "id": str(snapshot.id),
                        "code": "VECTOR_SNAPSHOT_BUILDING",
                    }
                ]
            )
        if snapshot.status != VECTOR_SNAPSHOT_READY or not snapshot.snapshot_hash:
            raise ConflictError(
                "Imported VectorSnapshot is not READY with immutable evidence"
            )
        return {
            "id": str(snapshot.id),
            "vector_snapshot_id": str(snapshot.id),
            "collection_id": str(snapshot.collection_id),
            "snapshot_hash": snapshot.snapshot_hash,
            "status": snapshot.status,
            "embedding_provider_model_id": str(snapshot.embedding_provider_model_id),
        }
