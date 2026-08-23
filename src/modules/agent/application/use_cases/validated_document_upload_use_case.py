from __future__ import annotations

import mimetypes
import zipfile
from io import BytesIO
from pathlib import PurePosixPath

from modules.agent.application.dtos.knowledge_dtos import (
    UploadDocumentFileInput,
    UploadDocumentInput,
    UploadDocumentOutput,
)
from modules.agent.application.use_cases.knowledge_use_cases import (
    ReadableUploadFile,
    UploadDocumentFileUseCase as BaseUploadDocumentFileUseCase,
    UploadDocumentUseCase as BaseUploadDocumentUseCase,
)
from modules.agent.domain.enums import ParserType
from shared.contracts.errors import NotFoundError, ValidationError


_EXTENSION_TO_PARSER = {
    ".txt": ParserType.TEXT,
    ".md": ParserType.MD,
    ".pdf": ParserType.PDF,
    ".docx": ParserType.DOCX,
}
_CONTENT_TYPES_BY_EXTENSION = {
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {
        "text/markdown",
        "text/plain",
        "text/x-markdown",
        "application/octet-stream",
    },
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
        "application/zip",
    },
}
_REQUIRED_DOCX_ENTRIES = {"[Content_Types].xml", "word/document.xml"}


class UploadDocumentUseCase(BaseUploadDocumentUseCase):
    async def execute(self, input_dto: UploadDocumentInput) -> UploadDocumentOutput:
        collection = await self.collection_repo.get_by_id(input_dto.collection_id)
        if collection.project_id != input_dto.project_id:
            raise NotFoundError("Document collection not found")
        return await super().execute(input_dto)


class UploadDocumentFileUseCase(BaseUploadDocumentFileUseCase):
    async def execute(
        self,
        input_dto: UploadDocumentFileInput,
        upload: ReadableUploadFile,
    ) -> UploadDocumentOutput:
        collection = await self.collection_repo.get_by_id(input_dto.collection_id)
        if collection.project_id != input_dto.project_id:
            raise NotFoundError("Document collection not found")
        return await super().execute(input_dto, upload)

    def _validate_extension(self, extension: str) -> ParserType:
        allowed = self._allowed_extensions()
        if extension not in allowed:
            supported = ", ".join(sorted(allowed))
            raise ValidationError(f"Only {supported} uploads are supported")
        parser = _EXTENSION_TO_PARSER.get(extension)
        if parser is None:
            raise ValidationError(f"Unsupported document extension: {extension}")
        return parser

    def _resolve_content_type(
        self,
        file_name: str,
        content_type: str | None,
        extension: str,
    ) -> str:
        guessed = mimetypes.guess_type(file_name)[0]
        normalized = (
            content_type or guessed or "application/octet-stream"
        ).split(";", 1)[0].strip().lower()
        if normalized not in _CONTENT_TYPES_BY_EXTENSION.get(extension, set()):
            raise ValidationError(
                f"Invalid content type for {extension}: {normalized or 'unknown'}"
            )
        if normalized in {"application/octet-stream", "application/zip"} and guessed:
            return guessed
        return normalized

    def _validate_content(self, content: bytes, extension: str) -> None:
        if not content:
            raise ValidationError("Uploaded file is empty")
        if len(content) > self._settings.upload_max_mb * 1024 * 1024:
            raise ValidationError(
                f"Uploaded file exceeds {self._settings.upload_max_mb} MB"
            )
        if extension == ".pdf" and not content.startswith(b"%PDF"):
            raise ValidationError("Uploaded file is not a valid PDF")
        if extension == ".docx":
            self._validate_docx(content)
        if extension in {".txt", ".md"}:
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationError(
                    "Text and Markdown uploads must be valid UTF-8"
                ) from exc

    def _validate_docx(self, content: bytes) -> None:
        max_entries = int(getattr(self._settings, "rag_docx_max_entries", 1000))
        max_uncompressed_mb = int(
            getattr(self._settings, "rag_docx_max_uncompressed_mb", 100)
        )
        max_compression_ratio = float(
            getattr(self._settings, "rag_docx_max_compression_ratio", 100.0)
        )

        try:
            with zipfile.ZipFile(BytesIO(content)) as package:
                entries = package.infolist()
                if len(entries) > max_entries:
                    raise ValidationError("DOCX contains too many package entries")
                names = {entry.filename for entry in entries}
                if not _REQUIRED_DOCX_ENTRIES.issubset(names):
                    raise ValidationError("Uploaded file is not a valid DOCX")

                total_uncompressed = 0
                max_uncompressed = max_uncompressed_mb * 1024 * 1024
                for entry in entries:
                    path = PurePosixPath(entry.filename)
                    if path.is_absolute() or ".." in path.parts:
                        raise ValidationError("DOCX contains an unsafe package path")
                    if entry.flag_bits & 0x1:
                        raise ValidationError("Encrypted DOCX documents are not supported")
                    total_uncompressed += entry.file_size
                    if total_uncompressed > max_uncompressed:
                        raise ValidationError(
                            "DOCX uncompressed content exceeds the allowed limit"
                        )
                    if entry.file_size > 0:
                        ratio = entry.file_size / max(entry.compress_size, 1)
                        if ratio > max_compression_ratio:
                            raise ValidationError(
                                "DOCX compression ratio exceeds the allowed limit"
                            )
        except ValidationError:
            raise
        except (zipfile.BadZipFile, OSError) as exc:
            raise ValidationError("Uploaded file is not a valid DOCX") from exc
