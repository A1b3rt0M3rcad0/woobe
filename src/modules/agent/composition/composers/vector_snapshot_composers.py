from __future__ import annotations

from modules.agent.application.dtos.vector_snapshot_dtos import (
    CreateVectorSnapshotInput,
    GetCollectionOverviewInput,
    GetVectorSnapshotInput,
    ListVectorSnapshotsInput,
    PreviewVectorSnapshotInput,
)
from modules.agent.application.use_cases.vector_snapshot_preview_use_case import (
    PreviewVectorSnapshotUseCase,
)
from modules.agent.application.use_cases.vector_snapshot_use_cases import (
    CreateVectorSnapshotUseCase,
    GetCollectionOverviewUseCase,
    GetVectorSnapshotUseCase,
    ListVectorSnapshotsUseCase,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.storage.factory import create_file_storage
from shared.infra.config import Settings


async def get_collection_overview(session_factory, input_dto: GetCollectionOverviewInput):
    async with AgentUnitOfWork(session_factory) as uow:
        return await GetCollectionOverviewUseCase(
            snapshot_repo=uow.vector_snapshots,
            collection_repo=uow.document_collections,
            document_repo=uow.documents,
        ).execute(input_dto)


async def preview_vector_snapshot(session_factory, input_dto: PreviewVectorSnapshotInput):
    storage = create_file_storage(Settings())
    async with AgentUnitOfWork(session_factory) as uow:
        return await PreviewVectorSnapshotUseCase(
            collection_repo=uow.document_collections,
            document_repo=uow.documents,
            storage=storage,
        ).execute(input_dto)


async def create_vector_snapshot(session_factory, input_dto: CreateVectorSnapshotInput):
    async with AgentUnitOfWork(session_factory) as uow:
        return await CreateVectorSnapshotUseCase(
            snapshot_repo=uow.vector_snapshots,
            collection_repo=uow.document_collections,
            document_repo=uow.documents,
            provider_model_repo=uow.provider_models,
            credential_repo=uow.provider_credentials,
        ).execute(input_dto)


async def list_vector_snapshots(session_factory, input_dto: ListVectorSnapshotsInput):
    async with AgentUnitOfWork(session_factory) as uow:
        return await ListVectorSnapshotsUseCase(uow.vector_snapshots).execute(input_dto)


async def get_vector_snapshot(session_factory, input_dto: GetVectorSnapshotInput):
    async with AgentUnitOfWork(session_factory) as uow:
        return await GetVectorSnapshotUseCase(uow.vector_snapshots).execute(input_dto)
