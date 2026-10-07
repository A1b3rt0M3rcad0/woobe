from sqlalchemy import select

from modules.agent.infra.database.models import DocumentCollectionModel
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel


class SQLProviderDependencyReader:
    def __init__(self, uow):
        self._uow = uow

    async def embedding_consumers(self, project_id, model_ids):
        if not model_ids:
            return []
        rows = (
            await self._uow.session.execute(
                select(VectorSnapshotModel, DocumentCollectionModel.name)
                .join(
                    DocumentCollectionModel,
                    DocumentCollectionModel.id == VectorSnapshotModel.collection_id,
                )
                .where(
                    VectorSnapshotModel.project_id == project_id,
                    DocumentCollectionModel.project_id == project_id,
                    VectorSnapshotModel.embedding_provider_model_id.in_(model_ids),
                    VectorSnapshotModel.status.not_in(
                        ["FAILED", "CANCELLED", "ARCHIVED"]
                    ),
                )
                .order_by(VectorSnapshotModel.id)
            )
        ).all()
        return [
            {
                "type": "vector_snapshot",
                "id": str(snapshot.id),
                "name": name,
                "status": snapshot.status,
                "field": "embedding_provider_model_id",
                "provider_model_id": str(snapshot.embedding_provider_model_id),
                "collection_id": str(snapshot.collection_id),
            }
            for snapshot, name in rows
        ]
