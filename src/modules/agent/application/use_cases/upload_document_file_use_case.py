from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from modules.agent.application.dtos.knowledge_dtos import UploadDocumentFileInput, UploadDocumentOutput
from modules.agent.application.use_cases.knowledge_use_cases import (
    ReadableUploadFile,
    UploadDocumentFileUseCase as BaseUploadDocumentFileUseCase,
    _as_value,
    _document_to_upload_output,
    _is_deleted_document,
)
from modules.agent.domain.entities import Document
from modules.agent.domain.enums import DocumentStatus
from modules.agent.domain.events import AgentDocumentUploadedV1
from modules.agent.domain.ports.file_storage import compute_sha256
from shared.infra.errors import ConflictError


class UploadDocumentFileUseCase(BaseUploadDocumentFileUseCase):
    async def execute(
        self,
        input_dto: UploadDocumentFileInput,
        upload: ReadableUploadFile,
    ) -> UploadDocumentOutput:
        await self.collection_repo.get_by_id(input_dto.collection_id)

        file_name = self._validate_file_name(upload.filename)
        extension = Path(file_name).suffix.lower()
        parser = self._validate_extension(extension)
        content_type = self._resolve_content_type(file_name, upload.content_type, extension)

        content = await upload.read()
        self._validate_content(content, extension)
        sha256 = compute_sha256(content)

        existing_documents = await self.doc_repo.list_by_collection(input_dto.collection_id)
        duplicate = next(
            (
                document
                for document in existing_documents
                if document.sha256 == sha256 and not _is_deleted_document(document)
            ),
            None,
        )
        if duplicate is not None:
            raise ConflictError("Document already exists in this collection")

        document_id = uuid4()
        stored = await self._storage.save_document(
            content=content,
            project_id=input_dto.project_id,
            collection_id=input_dto.collection_id,
            document_id=document_id,
            file_name=file_name,
            content_type=content_type,
        )

        title = (input_dto.title or "").strip() or Path(stored.file_name).stem
        document = Document(
            id=document_id,
            project_id=input_dto.project_id,
            collection_id=input_dto.collection_id,
            title=title,
            file_name=stored.file_name,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            storage_key=stored.storage_key,
            parser=parser,
            status=DocumentStatus.UPLOADED,
            sha256=sha256,
        )

        try:
            created = await self.doc_repo.create(document)
            event = AgentDocumentUploadedV1.create(
                document_id=created.id,
                collection_id=created.collection_id,
                project_id=created.project_id,
                file_name=created.file_name,
                storage_key=created.storage_key,
                parser=str(_as_value(created.parser)),
                payload={
                    "content_type": created.content_type,
                    "size_bytes": created.size_bytes,
                    "sha256": created.sha256,
                    "storage_driver": self._settings.storage_driver,
                },
            )
            await self._outbox.write(event)
        except Exception:
            await self._storage.delete(stored.storage_key)
            raise

        return _document_to_upload_output(created)
