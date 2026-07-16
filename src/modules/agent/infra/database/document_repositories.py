from modules.agent.infra.database.repositories import SQLAlchemyDocumentRepository
from modules.agent.infra.database.vector_snapshot_repositories import SQLAlchemyVectorSnapshotRepository


class SQLAlchemyGuardedDocumentRepository(SQLAlchemyDocumentRepository):
    async def has_active_vector_build(self, project_id, collection_id) -> bool:
        snapshots = SQLAlchemyVectorSnapshotRepository(self._session_or_uow)
        active = await snapshots.get_active_building_by_collection(project_id, collection_id)
        return active is not None
