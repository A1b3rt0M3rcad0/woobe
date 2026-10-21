from modules.artifacts.composition.resources import DATABASE_ENGINE
from modules.artifacts.infra.database.run_sources import RunSourceRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


async def record_run_source(scope, workspace_id, run_id, catalog_version, source):
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    async with uow:
        return await RunSourceRepository(uow).record(
            scope, workspace_id, run_id, catalog_version, source)


async def get_run_source_manifest(scope, workspace_id, run_id):
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    async with uow:
        return await RunSourceRepository(uow).get(scope, workspace_id, run_id)
