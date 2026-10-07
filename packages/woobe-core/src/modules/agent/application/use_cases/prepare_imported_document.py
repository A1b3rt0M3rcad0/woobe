from uuid import uuid4

from modules.agent.application.dtos.knowledge_dtos import UploadDocumentInput
from modules.agent.application.interfaces.file_storage import (
    FileStorage,
    compute_sha256,
)
from modules.agent.application.use_cases.knowledge_use_cases import (
    DocumentUploadPolicy,
    UploadSettings,
)


class PrepareImportedDocumentUseCase:
    def __init__(self, storage: FileStorage, settings: UploadSettings):
        self._storage, self._settings = storage, settings

    async def execute(
        self, *, project_id, collection_id, file_name, title, content, content_type=None
    ):
        """Validate and store captured bytes outside SQL; the owner registers them later."""
        name, media, parser = DocumentUploadPolicy(self._settings).prepare(
            file_name=file_name, content_type=content_type, content=content
        )
        identifier = uuid4()
        stored = await self._storage.save_document(
            content=content,
            project_id=project_id,
            collection_id=collection_id,
            document_id=identifier,
            file_name=name,
            content_type=media,
        )
        prepared = UploadDocumentInput(
            document_id=identifier,
            sha256=compute_sha256(content),
            project_id=project_id,
            collection_id=collection_id,
            title=title,
            file_name=stored.file_name,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            storage_key=stored.storage_key,
            parser=parser,
        ).model_dump(mode="json")
        # A newly allocated ID is not an existing resource selector. Keep it
        # distinct while authorization verifies the captured Project/Collection.
        prepared["new_document_id"] = prepared.pop("document_id")
        return prepared
