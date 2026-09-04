from __future__ import annotations

from uuid import UUID

from fastapi import UploadFile

from modules.agent.entrypoint import UploadDocumentFileInput
from modules.agent.entrypoint import (
    delete_document_composer,
)
from modules.agent.entrypoint import (
    upload_document_file_composer,
)
from woobe_api.http.shared.adapters import response_adapter


async def upload_document_file(
    *,
    project_id: UUID,
    collection_id: UUID,
    title: str | None,
    file: UploadFile,
):
    handler = upload_document_file_composer()
    response = await handler(
        (
            UploadDocumentFileInput(
                project_id=project_id,
                collection_id=collection_id,
                title=title,
            ),
            file,
        )
    )
    return response_adapter(response)


async def delete_document(*, document_id: UUID):
    handler = delete_document_composer()
    response = await handler(document_id)
    return response_adapter(response)

