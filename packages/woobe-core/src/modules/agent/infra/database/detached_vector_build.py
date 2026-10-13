"""Short owner transactions around a vector build's external work.

Progress is durable. Chunks, document projections and READY commit together only
while this worker still owns the build and frozen documents remain unchanged.
"""
from copy import deepcopy
from modules.agent.domain.vector_configuration import verify_vector_configuration

from sqlalchemy import select

from modules.agent.application.interfaces.project_configuration import configuration_for_session, resolve_runtime_configuration
from modules.agent.infra.adapters.configuration_bindings import provider_dependencies
from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential
from modules.agent.infra.database.models import DocumentModel
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyProviderModelRepository
from modules.agent.infra.database.repositories import SQLAlchemyDocumentRepository, SQLAlchemyProviderCredentialRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel
from modules.agent.infra.database.vector_snapshot_repositories import SQLAlchemyVectorSnapshotRepository
from shared.contracts.errors import ConflictError
from shared.contracts.project_configuration import ConfigurationError
from shared.contracts.time import utc_now
from shared.security.crypto import decrypt_secret


class _DetachedReadRepository:
    def __init__(self, uow_factory, repository):
        self.uow_factory, self.repository = uow_factory, repository

    async def get_by_id(self, identifier):
        async with self.uow_factory().mark_read_only() as uow:
            return await self.repository(uow).get_by_id(identifier)

    async def list_by_collection(self, identifier):
        async with self.uow_factory().mark_read_only() as uow:
            return await self.repository(uow).list_by_collection(identifier)


class _StagedDocuments(_DetachedReadRepository):
    def __init__(self, uow_factory):
        super().__init__(uow_factory, SQLAlchemyDocumentRepository)
        self.originals, self.updates = {}, {}

    async def get_by_id(self, identifier):
        document = await super().get_by_id(identifier)
        if document is not None:
            self.originals[identifier] = deepcopy(document)
        return document

    async def update(self, document):
        self.updates[document.id] = deepcopy(document)
        return document


class _StagedSnapshots(_DetachedReadRepository):
    def __init__(self, uow_factory, worker_id, documents):
        super().__init__(uow_factory, SQLAlchemyVectorSnapshotRepository)
        self.worker_id, self.documents = worker_id, documents
        self.chunks, self.counts = [], {}
        self.replacement_id = None

    async def _owned(self, uow, snapshot_id):
        row = await uow.session.scalar(select(VectorSnapshotModel).where(VectorSnapshotModel.id == snapshot_id).with_for_update())
        if row is None or row.status != "BUILDING" or row.locked_by != self.worker_id:
            raise ConflictError("Vector snapshot build ownership changed")
        return row

    async def mark_started(self, snapshot_id):
        # Host claims and marks the build before external work begins.
        async with self.uow_factory().mark_read_only() as uow:
            await self._owned(uow, snapshot_id)

    async def mark_failed(self, snapshot_id, error):
        # Host persists a sanitized error under the same ownership guard.
        pass

    async def update_build_progress(self, snapshot_id, **updates):
        async with self.uow_factory() as uow:
            row = await self._owned(uow, snapshot_id)
            await self.repository(uow).update_build_progress(snapshot_id, **updates)
            row.locked_at = utc_now()

    async def list_snapshot_documents(self, snapshot_id):
        async with self.uow_factory().mark_read_only() as uow:
            return await self.repository(uow).list_snapshot_documents(snapshot_id)

    async def add_snapshot_documents(self, documents):
        if not documents:
            return
        async with self.uow_factory() as uow:
            await self._owned(uow, documents[0].vector_snapshot_id)
            await self.repository(uow).add_snapshot_documents(documents)

    async def update_snapshot_document_chunk_count(self, snapshot_id, document_id, count):
        self.counts[snapshot_id, document_id] = count

    async def delete_snapshot_chunks(self, snapshot_id):
        self.replacement_id = snapshot_id
        self.chunks.clear()

    async def add_snapshot_chunks(self, chunks):
        self.chunks.extend(chunks)

    async def mark_ready(self, snapshot_id, **evidence):
        async with self.uow_factory() as uow:
            await self._owned(uow, snapshot_id)
            repository = self.repository(uow)
            documents = SQLAlchemyDocumentRepository(uow)
            for identifier in sorted(self.documents.originals, key=str):
                original = self.documents.originals[identifier]
                row = await uow.session.get(DocumentModel, identifier, with_for_update=True)
                if row is None or row.sha256 != original.sha256 or row.updated_at != original.updated_at or row.storage_key != original.storage_key:
                    raise ConflictError("Frozen vector document changed during preparation")
            for document in self.documents.updates.values():
                await documents.update(document)
            for (owner, document_id), count in self.counts.items():
                if owner != snapshot_id:
                    raise ConflictError("Vector snapshot result scope differs")
                await repository.update_snapshot_document_chunk_count(owner, document_id, count)
            if self.replacement_id != snapshot_id:
                raise ConflictError("Vector snapshot replacement scope differs")
            await repository.delete_snapshot_chunks(snapshot_id)
            await repository.add_snapshot_chunks(self.chunks)
            return await repository.mark_ready(snapshot_id, **evidence)


class DetachedVectorBuild:
    def __init__(self, *, engine, worker_id, storage, embedding_factory, encryption_key, use_case_factory):
        self.use_case_factory = use_case_factory
        self.uow_factory = lambda: AgentUnitOfWork(engine)
        self.worker_id, self.storage = worker_id, storage
        self.embedding_factory, self.encryption_key = embedding_factory, encryption_key

    async def _credential(self, snapshot, model, credential):
        if model.project_id != snapshot.project_id or credential.project_id != snapshot.project_id or str(getattr(credential.status, "value", credential.status)) != "active":
            raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
        verify_vector_configuration(snapshot, model, credential)
        if credential.authentication is None:
            return decrypt_secret(credential.encrypted_secret, self.encryption_key)
        base_url = (model.metadata or {}).get("base_url") or (credential.metadata or {}).get("base_url")
        async with self.uow_factory() as uow:
            port = configuration_for_session(uow.session)
            if port is None:
                raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
            await port.acquire(project_id=snapshot.project_id, run_id=snapshot.id,
                environment=(getattr(snapshot, "preparation_environment", None) or "draft"),
                dependencies=provider_dependencies(credential, base_url=base_url))
        async def resolve(destination):
            return await resolve_runtime_configuration(project_id=snapshot.project_id, run_id=snapshot.id,
                consumer_kind="provider_credential", consumer_id=credential.id,
                field_path="/authentication/fields/api_key", destination=destination)
        return BoundConfigurationCredential(resolve)

    async def execute(self, snapshot_id):
        documents = _StagedDocuments(self.uow_factory)
        snapshots = _StagedSnapshots(self.uow_factory, self.worker_id, documents)
        use_case = self.use_case_factory(snapshot_repo=snapshots, document_repo=documents,
            provider_model_repo=_DetachedReadRepository(self.uow_factory, SQLAlchemyProviderModelRepository),
            credential_repo=_DetachedReadRepository(self.uow_factory, SQLAlchemyProviderCredentialRepository),
            storage=self.storage, embedding_factory=self.embedding_factory, encryption_key=self.encryption_key,
            resolve_credential=self._credential)
        return await use_case.execute(snapshot_id)
