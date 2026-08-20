from __future__ import annotations

from uuid import UUID

from fastapi import UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from modules.agent.application.dtos import UploadDocumentFileInput
from modules.agent.application.use_cases import DeleteDocumentUseCase, UploadDocumentFileUseCase
from modules.agent.domain.errors import DocumentNotFoundError
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.storage.factory import create_file_storage
from modules.agent.presentation.mappers import upload_document_output_to_response
from shared.contracts.errors import ConflictError, ValidationError


async def upload_document_file(
    *,
    session_factory,
    settings,
    project_id: UUID,
    collection_id: UUID,
    title: str | None,
    file: UploadFile,
):
    storage = create_file_storage(settings)
    try:
        async with AgentUnitOfWork(session_factory) as uow:
            use_case = UploadDocumentFileUseCase(
                doc_repo=uow.documents,
                collection_repo=uow.document_collections,
                outbox=SQLAlchemyAgentOutboxEventWriter(uow),
                storage=storage,
                settings=settings,
            )
            output = await use_case.execute(
                UploadDocumentFileInput(
                    project_id=project_id,
                    collection_id=collection_id,
                    title=title,
                ),
                file,
            )
    except ConflictError as exc:
        return JSONResponse(
            status_code=409,
            content={"success": False, "message": str(exc), "data": None},
        )
    except ValidationError as exc:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(exc), "data": None},
        )

    return jsonable_encoder(
        {
            "success": True,
            "message": "created",
            "data": upload_document_output_to_response(output).model_dump(),
        }
    )


async def delete_document(*, session_factory, settings, document_id: UUID):
    storage = create_file_storage(settings)
    try:
        async with AgentUnitOfWork(session_factory) as uow:
            use_case = DeleteDocumentUseCase(
                doc_repo=uow.documents,
                chunk_repo=uow.document_chunks,
                storage=storage,
            )
            await use_case.execute(document_id)
    except DocumentNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Document not found", "data": None},
        )

    return {"success": True, "message": "Document deleted", "data": None}
