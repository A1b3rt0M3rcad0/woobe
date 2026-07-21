from __future__ import annotations

import zipfile
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pypdf import PdfWriter

from modules.agent.application.dtos.knowledge_dtos import UploadDocumentFileInput
from modules.agent.application.services.rag.document_parser import DocumentParser
from modules.agent.application.use_cases.validated_document_upload_use_case import (
    UploadDocumentFileUseCase,
)
from modules.agent.domain.entities import DocumentCollection
from modules.agent.domain.enums import ParserType
from shared.infra.errors import NotFoundError, ValidationError


_WORD_DOCUMENT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
      <w:r><w:t>Overview</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>Hello</w:t></w:r>
      <w:r><w:t xml:space="preserve"> world</w:t></w:r>
    </w:p>
    <w:tbl>
      <w:tr>
        <w:tc><w:p><w:r><w:t>Column A</w:t></w:r></w:p></w:tc>
        <w:tc><w:p><w:r><w:t>Column B</w:t></w:r></w:p></w:tc>
      </w:tr>
    </w:tbl>
  </w:body>
</w:document>
"""


def _docx_bytes(document_xml: str = _WORD_DOCUMENT) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as package:
        package.writestr(
            "[Content_Types].xml",
            "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>",
        )
        package.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _blank_pdf_bytes() -> bytes:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    return buffer.getvalue()


def _settings(**overrides):
    values = {
        "upload_allowed_extensions": ".txt,.md,.pdf,.docx",
        "upload_max_mb": 25,
        "rag_docx_max_entries": 1000,
        "rag_docx_max_uncompressed_mb": 100,
        "rag_docx_max_compression_ratio": 100.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _upload_use_case(settings=None) -> UploadDocumentFileUseCase:
    return UploadDocumentFileUseCase(
        doc_repo=SimpleNamespace(),
        collection_repo=SimpleNamespace(),
        outbox=SimpleNamespace(),
        storage=SimpleNamespace(),
        settings=settings or _settings(),
    )


def test_docx_parser_preserves_headings_run_whitespace_and_tables() -> None:
    parsed = DocumentParser().parse(
        content=_docx_bytes(),
        parser=ParserType.DOCX,
        file_name="knowledge.docx",
    )

    assert parsed.page_count is None
    assert "# Overview" in parsed.text
    assert "Hello world" in parsed.text
    assert "Column A | Column B" in parsed.text


def test_docx_parser_rejects_documents_without_extractable_text() -> None:
    empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p/></w:body>
    </w:document>
    """

    with pytest.raises(ValidationError, match="extractable text"):
        DocumentParser().parse(
            content=_docx_bytes(empty_xml),
            parser=ParserType.DOCX,
            file_name="empty.docx",
        )


def test_pdf_parser_reports_scanned_or_empty_documents() -> None:
    with pytest.raises(ValidationError, match="scanned PDFs require OCR"):
        DocumentParser().parse(
            content=_blank_pdf_bytes(),
            parser=ParserType.PDF,
            file_name="scan.pdf",
        )


def test_docx_upload_validation_checks_package_structure() -> None:
    use_case = _upload_use_case()

    assert use_case._validate_extension(".docx") == ParserType.DOCX
    assert (
        use_case._resolve_content_type(
            "knowledge.docx",
            "application/octet-stream",
            ".docx",
        )
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    use_case._validate_content(_docx_bytes(), ".docx")

    with pytest.raises(ValidationError, match="valid DOCX"):
        use_case._validate_content(b"not-a-docx", ".docx")


def test_pdf_upload_validation_checks_magic_bytes() -> None:
    use_case = _upload_use_case()

    use_case._validate_content(_blank_pdf_bytes(), ".pdf")
    with pytest.raises(ValidationError, match="valid PDF"):
        use_case._validate_content(b"not-a-pdf", ".pdf")


def test_docx_upload_validation_rejects_excessive_package_entries() -> None:
    use_case = _upload_use_case(_settings(rag_docx_max_entries=1))

    with pytest.raises(ValidationError, match="too many package entries"):
        use_case._validate_content(_docx_bytes(), ".docx")


@pytest.mark.asyncio
async def test_upload_rejects_collection_from_another_project() -> None:
    expected_project_id = uuid4()
    collection_id = uuid4()

    class CollectionRepository:
        async def get_by_id(self, requested_collection_id):
            assert requested_collection_id == collection_id
            return DocumentCollection(
                id=collection_id,
                project_id=uuid4(),
                name="Other project",
            )

    use_case = UploadDocumentFileUseCase(
        doc_repo=SimpleNamespace(),
        collection_repo=CollectionRepository(),
        outbox=SimpleNamespace(),
        storage=SimpleNamespace(),
        settings=_settings(),
    )
    upload = SimpleNamespace(
        filename="knowledge.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    with pytest.raises(NotFoundError, match="Document collection not found"):
        await use_case.execute(
            UploadDocumentFileInput(
                project_id=expected_project_id,
                collection_id=collection_id,
                title="Knowledge",
            ),
            upload,
        )
